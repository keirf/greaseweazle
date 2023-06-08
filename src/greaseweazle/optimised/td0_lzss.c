/*
 * TD02IMD - Convert Teledisk .TD0 images to ImageDisk .IMD format
 *
 * TD02IMD reads a teledisk .TD0 image file, and reformats it into an
 * ImageDisk .IMD file.
 *
 * Note that the Teledisk file format is closed and completely undocumented.
 * TD02IMD relies on information obtained by reverse engineering and may not
 * be able to handle all Teledisk images. I have included my notes on the
 * Teledisk file format in the file TD0NOTES.TXT
 *
 * This program is compiled using my own development tools, and will not
 * build under mainstream compilers without significant work. This source
 * code is provided for informational purposes only, and I provide no
 * support for it, technical or otherwise.
 *
 * Copyright 2007-2008 Dave Dunfield
 * All rights reserved.
 *
 * For the record: I am retaining copyright on this code, however this is
 * for the purpose of keeping a say in it's disposition. I encourage the
 * use of ideas, algorithms and code fragments contained herein to be used
 * in the creation of compatible programs on other platforms (eg: Linux).
 * 
 * Greaseweazle: This copy of the file was taken from HxCFloppyEmulator
 * and then lightly modified to fit the Greaseweazle project.
 *  - Keir Fraser
 */

#include <string.h>
#include <stdlib.h>
#include <stdint.h>

// LZSS parameters
#define SBSIZE        4096                // Size of Ring buffer
#define LASIZE        60                    // Size of Look-ahead buffer
#define THRESHOLD    2                    // Minimum match for compress

// Huffman coding parameters
#define N_CHAR    (256-THRESHOLD+LASIZE)    // Character code (= 0..N_CHAR-1)
#define TSIZE        (N_CHAR*2-1)        // Size of table
#define ROOT        (TSIZE-1)            // Root position
#define MAX_FREQ    0x8000                // Update when cumulative frequency reaches this value

static unsigned short
    parent[TSIZE+N_CHAR],    // parent nodes (0..T-1) and leaf positions (rest)
    son[TSIZE],                // pointers to child nodes (son[], son[]+1)
    freq[TSIZE+1],            // frequency table
    Bits, Bitbuff,            // buffered bit count and left-aligned bit buffer
    GBcheck,                // Getbyte check down-counter
    GBr,                    // Ring buffer position
    GBi,                    // Decoder index
    GBj,                    // Decoder index
    GBk;                    // Decoder index

static unsigned char
    GBstate,                // Decoder state
    Eof,                    // End-of-file indicator
    ring_buff[SBSIZE+LASIZE-1];    // text buffer for match strings

static int buffer_offset;
static int buffer_size;
static unsigned char * buffer_ptr;


/*
 * LZSS decoder - based in part on Haruhiko Okumura's LZHUF.C
 */

static const unsigned char d_code_lzss[256] = {        // Huffman decoder tables
0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03,
0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05, 0x05,
0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07, 0x07,
0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x08, 0x09, 0x09, 0x09, 0x09, 0x09, 0x09, 0x09, 0x09,
0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0A, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B, 0x0B,
0x0C, 0x0C, 0x0C, 0x0C, 0x0D, 0x0D, 0x0D, 0x0D, 0x0E, 0x0E, 0x0E, 0x0E, 0x0F, 0x0F, 0x0F, 0x0F,
0x10, 0x10, 0x10, 0x10, 0x11, 0x11, 0x11, 0x11, 0x12, 0x12, 0x12, 0x12, 0x13, 0x13, 0x13, 0x13,
0x14, 0x14, 0x14, 0x14, 0x15, 0x15, 0x15, 0x15, 0x16, 0x16, 0x16, 0x16, 0x17, 0x17, 0x17, 0x17,
0x18, 0x18, 0x19, 0x19, 0x1A, 0x1A, 0x1B, 0x1B, 0x1C, 0x1C, 0x1D, 0x1D, 0x1E, 0x1E, 0x1F, 0x1F,
0x20, 0x20, 0x21, 0x21, 0x22, 0x22, 0x23, 0x23, 0x24, 0x24, 0x25, 0x25, 0x26, 0x26, 0x27, 0x27,
0x28, 0x28, 0x29, 0x29, 0x2A, 0x2A, 0x2B, 0x2B, 0x2C, 0x2C, 0x2D, 0x2D, 0x2E, 0x2E, 0x2F, 0x2F,
0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F };

static const unsigned char d_len_lzss[] = { 2, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7 };

/*
 * Initialise the decompressor trees and state variables
 */
static void init_decompress(void)
{
    unsigned short i, j;

    memset(&parent,0,(TSIZE+N_CHAR)*2);
    memset(&son,0, (TSIZE)*2);
    memset(&freq,0,(TSIZE+1)*2);
    Bits=0;
    Bitbuff=0;
    GBcheck=0;
    GBr=0;
    GBi=0;
    GBj=0;
    GBk=0;

    GBstate=0;
    Eof=0;
    memset(&ring_buff,0,SBSIZE+LASIZE-1);


    for(i = j = 0; i < N_CHAR; ++i) {        // Walk up
        freq[i] = 1;
        son[i] = i + TSIZE;
        parent[i+TSIZE] = i; }

    while(i <= ROOT) {                        // Back down
        freq[i] = freq[j] + freq[j+1];
        son[i] = j;
        parent[j] = parent[j+1] = i++;
        j += 2; }

    memset(ring_buff, ' ',(SBSIZE+LASIZE-1));
    freq[TSIZE] = 0xFFFF;
    parent[ROOT] = Bitbuff = Bits = 0;
    GBr = SBSIZE - LASIZE;
}

/*
 * Increment frequency tree entry for a given code
 */
static void lzss_update(int c)
{
    unsigned short i, j, k, f, l;

    if(freq[ROOT] == MAX_FREQ) {        // Tree is full - rebuild
        // Halve cumulative freq for leaf nodes
        for(i = j = 0; i < TSIZE; ++i) {
            if(son[i] >= TSIZE) {
                freq[j] = (freq[i] + 1) / 2;
                son[j] = son[i];
                ++j; } }

        // make a tree - first connect children nodes
        for(i = 0, j = N_CHAR; j < TSIZE; i += 2, ++j) {
            k = i + 1;
            f = freq[j] = freq[i] + freq[k];
            for(k = j - 1; f < freq[k]; --k);
            ++k;
            l = (j - k) * sizeof(unsigned short);

            memmove(&freq[k+1], &freq[k], l);
            freq[k] = f;
            memmove(&son[k+1], &son[k], l);
            son[k] = i; }

        // Connect parent nodes
        for(i = 0 ; i < TSIZE ; ++i)
            if((k = son[i]) >= TSIZE)
                parent[k] = i;
            else
                parent[k] = parent[k+1] = i; }

    c = parent[c+TSIZE];
    do {
        k = ++freq[c];
        // Swap nodes if necessary to maintain frequency ordering
        if(k > freq[l = c+1]) {
            while(k > freq[++l]);
            freq[c] = freq[--l];
            freq[l] = k;
            parent[i = son[c]] = l;
            if(i < TSIZE)
                parent[i+1] = l;
            parent[j = son[l]] = c;
            son[l] = i;
            if(j < TSIZE)
                parent[j+1] = c;
            son[c] = j;
            c = l; }

            c = parent[c];
    } while(c);    // Repeat up to root
}

/*
 * Get a byte from the input file and flag Eof at end
 */
static unsigned short GetChar(void)
{
    unsigned char c;
    c=buffer_ptr[buffer_offset];
    buffer_offset++;
    if(buffer_offset>=buffer_size)
    {
        buffer_offset=buffer_size-1;
        c = 0;
        Eof = 1;
    }
    return (unsigned short)(c&0xFF);
}

/*
 * Get a single bit from the input stream
 */
static unsigned short GetBit(void)
{
    unsigned short t;
    if(!Bits--) {
        Bitbuff |= GetChar() << 8;
        Bits = 7; }

    t = Bitbuff >> 15;
    Bitbuff <<= 1;
    return t;
}
/*
 * Get a byte from the input stream - NOT bit-aligned
 */
static unsigned short GetByte(void)
{
    unsigned short t;
    if(Bits < 8)
        Bitbuff |= GetChar() << (8-Bits);
    else
        Bits -= 8;

    t = Bitbuff >> 8;
    Bitbuff <<= 8;
    return t;
}

/*
 * Decode a character value from table
 */
static unsigned short lzss_DecodeChar(void)
{
    unsigned short c;

    // search the tree from the root to leaves.
    // choose node #(son[]) if input bit == 0
    // choose node #(son[]+1) if input bit == 1
    c = ROOT;
    while((c = son[c]) < TSIZE)
        c += GetBit();

    lzss_update(c -= TSIZE);
    return c;
}

/*
 * Decode a compressed string index from the table
 */
static unsigned short lzss_DecodePosition(void)
{
    unsigned short i, j, c;

    // Decode upper 6 bits from given table
    i = GetByte();
    c = d_code_lzss[i] << 6;

    // input lower 6 bits directly
    j = d_len_lzss[i >> 4];
    while(--j)
        i = (i << 1) | GetBit();

    return (i & 0x3F) | c;
}


/*
 * Get a byte from the input file - decompress if required
 *
 * This implements a state machine to perform the LZSS decompression
 * allowing us to decompress the file "on the fly", without having to
 * have it all in memory.
 */
static int getbyte(void)
{
    unsigned short c;

    --GBcheck;

    for(;;) {                // Decompressor state machine
        if(Eof)                    // End of file has been flagged
            return -1;
        if(!GBstate) {            // Not in the middle of a string
            c = lzss_DecodeChar();
            if(c < 256) {        // Direct data extraction
                ring_buff[GBr++] = (unsigned char)c;
                GBr &= (SBSIZE-1);
                return c; }
            GBstate = 255;        // Begin extracting a compressed string
            GBi = (GBr - lzss_DecodePosition() - 1) & (SBSIZE-1);
            GBj = c - 255 + THRESHOLD;
            GBk = 0; }
        if(GBk < GBj) {            // Extract a compressed string
            ring_buff[GBr] = ring_buff[(GBk++ + GBi) & (SBSIZE-1)];
            c = ring_buff[GBr++];

            GBr &= (SBSIZE-1);
            return c; }
        GBstate = 0; }            // Reset to non-string state
}

uint8_t *td0_unpack(uint8_t *packeddata, unsigned int size,
                    unsigned int *unpacked_size)
{

    unsigned char *buffer;
    int i = 0;

    init_decompress();

    buffer_ptr = packeddata;
    buffer_size = size;
    buffer_offset = 0;

    buffer = (unsigned char*)malloc(512);
    while (!Eof && buffer) {
        do {
            buffer[i++] = getbyte();
        } while((i&511) && !Eof);
        buffer = (unsigned char*)realloc( buffer,i+512);
    }

    *unpacked_size = i;
    return buffer;
}
