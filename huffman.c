#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <err.h>
#include <math.h>

static int verbose = 0;
static double tot_entropy = 0.0;

/* 8-bit alphabet plus an escape code for emitting symbols not represented in
 * the Huffman tree, and an end-of-stream code to exit the decoder. */
#define NR_SYMBOLS 258
#define SYM_ESC    256
#define SYM_EOS    257

/* LUT: 8-bit code prefix -> Huffman tree node or leaf. */
#define lent_codelen(e) ((e)>>16)
#define lent_node(e) ((uint16_t)(e))
#define mk_lent(node, codelen) (((codelen)<<16)|(node))
typedef uint32_t lent_t;
typedef lent_t *lut_t;

/* Dict: input symbol -> { code, codelen }. */
#define dent_codelen(e) ((e)>>16)
#define dent_code(e) ((uint16_t)(e))
#define mk_dent(code, codelen) (((codelen)<<16)|(code))
typedef uint32_t dent_t;
typedef dent_t *dict_t;

/* A node can be a leaf or internal. Only internal nodes have child links. */
#define NODE_INTERNAL 0x8000
#define node_is_internal(n) ((n) & NODE_INTERNAL)
#define node_is_leaf(n) !node_is_internal(n)
#define node_idx(n) ((n) & 0x7fff)

/* Internal Huffman tree node. */
#define node_left(e) ((e)>>16)
#define node_right(e) ((uint16_t)(e))
#define mk_node(l,r) (((l)<<16)|(r))
typedef uint32_t node_t;

/* Heap: Min-heap used for constructing the Huffman tree. */
#define hent_count(e) ((uint16_t)(e))
#define hent_node(e) ((e)>>16)
#define mk_hent(node, count) (((node)<<16)|(count))
typedef uint32_t hent_t;
typedef hent_t *heap_t; /* [0] -> nr */

struct huffman_state {
    node_t nodes[NR_SYMBOLS]; /* 258 * 4 bytes */
    union {
        hent_t heap[NR_SYMBOLS+1]; /* 259 * 4 bytes */
        lent_t lut[256]; /* 256 * 4 bytes */
        dent_t dict[NR_SYMBOLS]; /* 258 * 4 bytes */
    } u; /* 259 * 4 bytes */
}; /* 517 * 4 = 2068 bytes */

/* Percolate item @i downwards to correct position among subheaps. */
static void heap_percolate_down(heap_t heap, unsigned int i)
{
    unsigned int nr = heap[0];
    uint32_t x = heap[i];
    for (;;) {
        unsigned int l = 2*i, r = 2*i+1, smallest = i;
        uint32_t s = x;
        /* Find the smallest of three nodes. */
        if ((l <= nr) && (hent_count(heap[l]) < hent_count(s))) {
            smallest = l;
            s = heap[l];
        }
        if ((r <= nr) && (hent_count(heap[r]) < hent_count(s))) {
            smallest = r;
            s = heap[r];
        }
        if (smallest == i)
            break;
        /* Swap with smallest subtree root. */
        heap[i] = s;
        heap[smallest] = x;
        /* Tail recursion (iteration) into the subtree we swapped with. */
        i = smallest;
    }
}

static void build_heap(heap_t heap, unsigned int nr)
{
    unsigned int i, j;
    for (i = j = 1; i <= nr; i++) {
        uint32_t he = heap[i];
        if (hent_count(he) != 0)
            heap[j++] = he;
    }
    heap[0] = --j;
    for (i = j/2; i > 0; i--)
        heap_percolate_down(heap, i);
}

static uint16_t build_huffman_tree(heap_t heap, node_t *nodes)
{
    unsigned int nr = heap[0];
    uint32_t x, y;

    for (;;) {
        /* heap_get_min #1 */
        x = heap[1];
        heap[1] = heap[nr];
        if ((heap[0] = --nr) == 0)
            break;
        heap_percolate_down(heap, 1);
        /* heap_get_min #2 */
        y = heap[1];
        nodes[nr] = mk_node(hent_node(x), hent_node(y));
        heap[1] = mk_hent(nr|NODE_INTERNAL, hent_count(x) + hent_count(y));
        heap_percolate_down(heap, 1);
    }

    return hent_node(x);
}

static uint16_t build_huffman_heap_and_tree(
    unsigned char *model_p, unsigned int model_nr, heap_t heap, node_t *nodes)
{
    uint32_t *h = &heap[1];
    unsigned int i;

    for (i = 0; i < 256; i++)
        h[i] = mk_hent(i, 0);
    h[SYM_ESC] = mk_hent(SYM_ESC, 1);
    h[SYM_EOS] = mk_hent(SYM_EOS, 1);
    for (i = 0; i < model_nr; i++)
        h[(unsigned int)model_p[i]]++;

    if (verbose) {
        printf("Frequencies:\n");
        for (i = 0; i < 256; i++)
            if (hent_count(h[i]))
                printf("%03x: %d\n", i, hent_count(h[i]));
        printf("\n");
    }

    build_heap(heap, NR_SYMBOLS);
    return build_huffman_tree(heap, nodes);
}

static char *prefix_str(uint32_t prefix, unsigned int prefix_len)
{
    static char s[33];
    int i;
    s[prefix_len] = '\0';
    for (i = prefix_len; i > 0; i--) {
        s[i-1] = '0' + (prefix&1);
        prefix >>= 1;
    }
    return s;
}

static void build_huffman_dict(uint16_t root, node_t *nodes, dict_t dict)
{
    uint16_t stack[32], node = root;
    unsigned int sp = 0, prefix_len = 0;
    uint32_t prefix = 0;

    memset(dict, 0, NR_SYMBOLS * sizeof(*dict));

    for (;;) {

        if (node_is_leaf(node)) {

            /* Visit leaf */
            dict[node] = mk_dent(prefix, prefix_len);
            if (verbose)
                printf("%03x: %d %s\n", node,
                       prefix_len, prefix_str(prefix, prefix_len));

            /* Visit ancestors until we follow a left-side link. */
            do {
                if (sp == 0) {
                    /* Returned to root via right-side link. We're done. */
                    return;
                }
                node = stack[--sp];
                prefix >>= 1;
                prefix_len--;
            } while (node == 0);

            /* Walk right-side link. Dummy on stack for tracking prefix. */
            stack[sp++] = 0;
            node = node_right(nodes[node_idx(node)]);
            prefix = (prefix<<1)|1;

        } else {

            /* Walk left-side link. */
            stack[sp++] = node;
            node = node_left(nodes[node_idx(node)]);
            prefix <<= 1;

        }

        prefix_len++;

    }
}

static void build_huffman_lut(uint16_t root, node_t *nodes, lut_t lut)
{
    uint16_t stack[32], node = root;
    unsigned int sp = 0, prefix_len = 0;
    uint32_t prefix = 0;

    for (;;) {

        if (node_is_leaf(node)) {

            /* Visit leaf */
            int idx = prefix << (8-prefix_len);
            int nr = 1 << (8-prefix_len);
            while (nr--)
                lut[idx+nr] = mk_lent(node, prefix_len);

        up:
            /* Visit ancestors until we follow a left-side link. */
            do {
                if (sp == 0) {
                    /* Returned to root via right-side link. We're done. */
                    return;
                }
                node = stack[--sp];
                prefix >>= 1;
                prefix_len--;
            } while (node == 0);

            /* Walk right-side link. Dummy on stack for tracking prefix. */
            stack[sp++] = 0;
            node = node_right(nodes[node_idx(node)]);
            prefix = (prefix<<1)|1;

        } else if (prefix_len == 8) {

            /* Reached max depth for LUT. */
            lut[prefix] = mk_lent(node, prefix_len);
            goto up;

        } else {

            /* Walk left-side link. */
            stack[sp++] = node;
            node = node_left(nodes[node_idx(node)]);
            prefix <<= 1;

        }

        prefix_len++;

    }
}

/* Shannon entropy of a string of 8-bit symbols. */
static double message_entropy(unsigned char *p, unsigned int nr)
{
    unsigned int i, counts[256] = { 0 };
    double entropy = 0.0;
    for (i = 0; i < nr; i++)
        counts[(unsigned int)p[i]]++;
    for (i = 0; i < 256; i++) {
        if (counts[i])
            entropy += counts[i] * log2((double)nr/counts[i]);
    }
    return entropy;
}

static int huffman_compress(
    struct huffman_state *state,
    unsigned char *model_p, unsigned int model_nr,
    unsigned char *msg_p, unsigned int msg_nr,
    unsigned char *out_p)
{
    dent_t dent;
    dict_t dict = state->u.dict;
    unsigned char *p;
    unsigned int i, tot, root, bits;
    double entropy, delta;
    uint32_t x;

    /* Verbatim please */
    if (model_p == NULL)
        goto verbatim;

    root = build_huffman_heap_and_tree(
        model_p, model_nr, state->u.heap, state->nodes);
    build_huffman_dict(root, state->nodes, dict);

    x = bits = 0;
    p = out_p + 2;
    for (i = 0; i < msg_nr; i++) {
        unsigned int symbol = msg_p[i];
        if ((dent = dict[symbol]) == 0) {
            dent = dict[SYM_ESC];
            x <<= dent_codelen(dent) + 8;
            x |= ((uint32_t)dent_code(dent) << 8) | symbol;
            bits += dent_codelen(dent) + 8;
        } else {
            x <<= dent_codelen(dent);
            x |= dent_code(dent);
            bits += dent_codelen(dent);
        }
        while (bits >= 8) {
            bits -= 8;
            *p++ = x >> bits;
        }
    }

    dent = dict[SYM_EOS];
    x <<= dent_codelen(dent);
    x |= dent_code(dent);
    bits += dent_codelen(dent);
    while (bits >= 8) {
        bits -= 8;
        *p++ = x >> bits;
    }
    if (bits)
        *p++ = x << (8 - bits);

    tot = p - out_p;
    out_p[0] = tot >> 8;
    out_p[1] = tot;
    if (tot > msg_nr+2) {
    verbatim:
        tot = msg_nr + 2;
        out_p[0] = (tot >> 8) | 0x80;
        out_p[1] = tot;
        memcpy(&out_p[2], msg_p, msg_nr);
    }

    printf("Encoded %4d -> %4d bytes (%6.2f%%);    ", msg_nr, tot,
           100.0*tot/(float)msg_nr);
    entropy = message_entropy(msg_p, msg_nr);
    printf("Entropy %7.2f bits, %4d bytes (%6.2f%%);    ",
           entropy, (int)ceil(entropy/8),
           100.0*(entropy/8)/(float)msg_nr);
    delta = (tot*8 - entropy);
    printf("Delta: %7.2f bits, %4d bytes (%6.2f%%)\n",
           delta, (int)ceil(delta/8), 100.0*(delta/8)/(float)msg_nr);
    tot_entropy += entropy;
    return tot;
}

static int huffman_decompress(
    struct huffman_state *state,
    unsigned char *model_p, unsigned int model_nr,
    unsigned char *msg_p, unsigned int msg_nr,
    unsigned char *out_p)
{
    lut_t lut = state->u.lut;
    node_t *nodes = state->nodes;
    unsigned char *p = msg_p, *q = out_p;
    unsigned int root, bits, node;
    uint32_t x;

    root = build_huffman_heap_and_tree(
        model_p, model_nr, state->u.heap, nodes);
    build_huffman_lut(root, nodes, lut);

    x = bits = 0;
    for (;;) {

        uint32_t entry;
        unsigned int codelen;

        while (bits < 24) {
            x |= (uint32_t)(*p++) << (24 - bits);
            bits += 8;
        }

        entry = lut[x >> 24];
        node = lent_node(entry);
        codelen = lent_codelen(entry);
        x <<= codelen; bits -= codelen;

        while (node_is_internal(node)) {
            entry = nodes[node_idx(node)];
            node = (int32_t)x < 0 ? node_right(entry) : node_left(entry);
            x <<= 1; bits--;
        }

        switch (node) {
        case SYM_EOS:
            goto out;
        case SYM_ESC: {
            node = x >> 24;
            x <<= 8; bits -= 8;
            /* fallthrough */
        }
        default:
            *q++ = node;
            break;
        }

    }

out:
    return q - out_p;
}

int main(int argc, char **argv)
{
#define NR 1024
    FILE *f;
    unsigned char *p, *prev_p = NULL;
    unsigned int off, size, nr, prev_nr = 0, out_nr = 0;
    unsigned char *in, *out;
    struct huffman_state huffman_state;

    if (argc != 3)
        errx(1, "Usage: %s <in> <out>", argv[0]);

    /* Read whole file to { p, size }. */
    if (!(f = fopen(argv[1], "rb")))
        err(1, NULL);
    fseek(f, 0, SEEK_END);
    size = ftell(f);
    fseek(f, 0, SEEK_SET);
    in = p = malloc(size+3); /* decompress may scan 3 bytes beyond */
    out = malloc(10*size); /* big enough */
    if (fread(p, 1, size, f) != size)
        err(1, NULL);
    fclose(f);

    if (strstr(argv[1], ".huf")) {

        /* DECOMPRESS */
        while ((p - in) < size) {
            int header = (p[0] << 8) | p[1];
            if (header & (1u<<15)) {
                /* verbatim */
                header &= 0x7fff;
                nr = header - 2;
                memcpy(&out[out_nr], p+2, nr);
            } else {
                /* compressed */
                nr = huffman_decompress(&huffman_state,
                                        prev_p, prev_nr, p+2, header-2,
                                        &out[out_nr]);
            }
            prev_p = &out[out_nr];
            prev_nr = nr;
            out_nr += nr;
            p += header;
        }

    } else {

        /* COMPRESS */
        for (off = 0; off < size; off += nr) {
            nr = (NR > (size-off)) ? size-off : NR;
            out_nr += huffman_compress(&huffman_state,
                                       prev_p, prev_nr, &p[off], nr,
                                       &out[out_nr]);
            prev_p = &p[off];
            prev_nr = nr;
        }

        printf("*** Entropy: %d bytes (%.2f%%); Encoded: %d bytes (%.2f%%); "
               "Original = %d bytes\n",
               (int)ceil(tot_entropy/8),
               100.0*(tot_entropy/8)/(float)size,
               out_nr,
               100.0*out_nr/(float)size, size);

    }

    free(in);
    if (!(f = fopen(argv[2], "wb")))
        err(1, NULL);
    if (fwrite(out, 1, out_nr, f) != out_nr)
        err(1, NULL);
    fclose(f);
    free(out);

    return 0;
}

/*
 * Local variables:
 * mode: C
 * c-file-style: "Linux"
 * c-basic-offset: 4
 * tab-width: 4
 * indent-tabs-mode: nil
 * End:
 */
