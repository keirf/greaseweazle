#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <err.h>
#include <math.h>

static int verbose = 0;

#define NR_SYMBOLS 258
#define SYM_ESC    256
#define SYM_EOS    257

struct dict {
    uint16_t len;
    uint16_t code;
};

struct node {
    uint16_t l, r;
    uint16_t count;
};

struct heap {
    uint16_t e[NR_SYMBOLS];
    uint16_t nr;
};

/* Builds heap at root i given that subtrees are both already heaps. */
void heapify(struct heap *heap, struct node *nodes, int i)
{
    for (;;) {
        int l= 2*i, r = 2*i+1, smallest = i;
        uint16_t t;
        /* Find the smallest of three nodes. */
        if ((l < heap->nr) &&
            (nodes[heap->e[l]].count < nodes[heap->e[smallest]].count))
            smallest = l;
        if ((r < heap->nr) &&
            (nodes[heap->e[r]].count < nodes[heap->e[smallest]].count))
            smallest = r;
        if (smallest == i)
            return;
        /* Swap with smallest subtree root. */
        t = heap->e[i];
        heap->e[i] = heap->e[smallest];
        heap->e[smallest] = t;
        /* Tail recursion (iteration) into the subtree we swapped with. */
        i = smallest;
    }
}

/* Build heap from scratch. */
void build_heap(struct heap *heap, struct node *nodes, int nr)
{
    int i, j;
    for (i = j = 0; i < nr; i++)
        if (nodes[i].count != 0)
            heap->e[j++] = i;
    heap->nr = j;
    for (i = j/2; i >= 0; i--)
        heapify(heap, nodes, i);
}

uint16_t heap_get_min(struct heap *heap, struct node *nodes)
{
    uint16_t x = heap->e[0];
    if (--heap->nr == 0)
        goto out;
    heap->e[0] = heap->e[heap->nr];
    heapify(heap, nodes, 0);
out:
    return x;
}

uint16_t build_huffman_tree(struct heap *heap, struct node *nodes)
{
    int next = NR_SYMBOLS;

    while (heap->nr != 1) {
        uint16_t x, y;
        x = heap_get_min(heap, nodes);
        y = heap->e[0];
        nodes[next].l = x;
        nodes[next].r = y;
        nodes[next].count = nodes[x].count + nodes[y].count;
        heap->e[0] = next;
        heapify(heap, nodes, 0);
        next++;
    }
    
    return heap->e[0];
}

char *prefix_str(uint32_t prefix, int prefix_len)
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

void build_huffman_dict(uint16_t root, struct node *nodes, struct dict *dict)
{
    uint16_t stack[32], node = root;
    int sp = 0;
    uint32_t prefix = 0;
    int prefix_len = 0;

    for (;;) {

        if (node < NR_SYMBOLS) {

            /* Visit leaf */
            dict[node].code = prefix;
            dict[node].len = prefix_len;
            if (verbose)
                printf("%03x: %d %d %s\n", node, nodes[node].count,
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
            node = nodes[node].r;
            prefix = (prefix<<1)|1;

        } else {

            /* Walk left-side link. */
            stack[sp++] = node;
            node = nodes[node].l;
            prefix <<= 1;

        }

        prefix_len++;

    }
}

/* Shannon entropy of a string of 8-bit symbols. */
double message_entropy(unsigned char *p, int nr)
{
    int i;
    int counts[256] = { 0 };
    double entropy = 0.0;
    for (i = 0; i < nr; i++)
        counts[(unsigned int)p[i]]++;
    for (i = 0; i < 256; i++) {
        if (counts[i])
            entropy += counts[i] * log2((double)nr/counts[i]);
    }
    return entropy;
}

double tot_entropy = 0.0;
int tot_msg = 0;

unsigned char *_window_output(unsigned char *p, uint32_t window, int window_bits)
{
    while (window_bits >= 8) {
        window_bits -= 8;
        *p++ = window >> window_bits;
    }
    return p;
}

#define window_output(p, window, window_bits) do {      \
    p = _window_output(p, window, window_bits);         \
    window_bits &= 7; } while (0);

int huffman(unsigned char *model_p, int model_nr,
            unsigned char *msg_p, int msg_nr,
            unsigned char *out_p)
{
    struct node nodes[NR_SYMBOLS*2];
    struct heap heap;
    struct dict dict[NR_SYMBOLS] = { 0 };
    unsigned char *p;
    int i, tot, root, window_bits;
    double entropy, delta;
    uint32_t window;

    /* Verbatim please */
    if (model_p == NULL)
        goto verbatim;

    memset(nodes, 0, sizeof(nodes));
    nodes[SYM_ESC].count = nodes[SYM_EOS].count = 1;
    for (i = 0; i < model_nr; i++)
        nodes[(unsigned int)model_p[i]].count++;

    if (verbose) {
        printf("Frequencies:\n");
        for (i = 0; i < 256; i++)
            if (nodes[i].count)
                printf("%03x: %d\n", i, nodes[i].count);
        printf("\n");
    }

    build_heap(&heap, nodes, NR_SYMBOLS);
    root = build_huffman_tree(&heap, nodes);
    build_huffman_dict(root, nodes, dict);

    window = window_bits = 0;
    p = out_p + 2;
    for (i = 0; i < msg_nr; i++) {
        unsigned int symbol = msg_p[i];
        if (dict[symbol].len == 0) {
            window <<= dict[SYM_ESC].len;
            window |= dict[SYM_ESC].code;
            window_bits += dict[SYM_ESC].len;
            window_output(p, window, window_bits);
            window <<= 8;
            window |= symbol;
            window_bits += 8;
        } else {
            window <<= dict[symbol].len;
            window |= dict[symbol].code;
            window_bits += dict[symbol].len;
        }
        window_output(p, window, window_bits);
    }

    window <<= dict[SYM_EOS].len;
    window |= dict[SYM_EOS].code;
    window_bits += dict[SYM_EOS].len;
    window_output(p, window, window_bits);
    if (window_bits) {
        window <<= 8 - window_bits;
        *p++ = window;
    }

    tot = p - out_p;
    out_p[0] = tot >> 8;
    out_p[1] = tot;
    if (tot > msg_nr+2) {
    verbatim:
        p = out_p;
        tot = msg_nr + 2;
        *p++ = (tot>>8) | 0x80;
        *p++ = tot;
        memcpy(p, msg_p, msg_nr);
        p += msg_nr;
    }

    printf("Encoded length %d bytes (%.2f%%)\n", tot,
           100.0*tot/(float)msg_nr);
    entropy = message_entropy(msg_p, msg_nr);
    printf("Entropy: %.2f bits (%d bytes) (%.2f%%)\n",
           entropy, (int)ceil(entropy/8),
           100.0*(entropy/8)/(float)msg_nr);
    delta = (tot*8 - entropy);
    printf("Delta: %.2f bits (%.2f%%)\n",
           delta, 100.0*(delta/8)/(float)msg_nr);
    tot_entropy += entropy;
    tot_msg += tot;
    return tot;
}

int huff_deco(unsigned char *model_p, int model_nr,
              unsigned char *msg_p, int msg_nr,
              unsigned char *out_p)
{
    struct node nodes[NR_SYMBOLS*2];
    struct heap heap;
    struct dict dict[NR_SYMBOLS] = { 0 };
    unsigned char *p, *q;
    int i, root, bits, node;
    int8_t x;

    memset(nodes, 0, sizeof(nodes));
    nodes[SYM_ESC].count = nodes[SYM_EOS].count = 1;
    for (i = 0; i < model_nr; i++)
        nodes[(unsigned int)model_p[i]].count++;

    if (verbose) {
        printf("Frequencies:\n");
        for (i = 0; i < 256; i++)
            if (nodes[i].count)
                printf("%03x: %d\n", i, nodes[i].count);
        printf("\n");
    }

    build_heap(&heap, nodes, NR_SYMBOLS);
    root = build_huffman_tree(&heap, nodes);
    build_huffman_dict(root, nodes, dict);

    p = msg_p;
    q = out_p;
    x = bits = 0;
    node = root;
    for (;;) {

        while (node >= NR_SYMBOLS) {
            if (bits == 0) {
                x = *p++;
                bits = 8;
            }
            node = x < 0 ? nodes[node].r : nodes[node].l;
            x <<= 1; bits--;
        }

        switch (node) {
        case SYM_EOS:
            goto out;
        case SYM_ESC: {
            int mask = (1u<<(8-bits))-1;
            node = x & ~mask;
            x = *p++;
            node |= (x>>bits) & mask;
            x <<= 8-bits;
            /* fallthrough */
        }
        default:
            *q++ = node;
            node = root;
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
    int off, size, nr, prev_nr = 0, out_nr = 0;
    unsigned char *in, *out;

    if (argc != 3)
        errx(1, "Usage: %s <in> <out>", argv[0]);

    /* Read whole file to { p, size }. */
    if (!(f = fopen(argv[1], "rb")))
        err(1, NULL);
    fseek(f, 0, SEEK_END);
    size = ftell(f);
    fseek(f, 0, SEEK_SET);
    in = p = malloc(size);
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
                nr = huff_deco(prev_p, prev_nr, p+2, header-2,
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
            out_nr += huffman(prev_p, prev_nr, &p[off], nr, &out[out_nr]);
            prev_p = &p[off];
            prev_nr = nr;
        }

        printf("FINAL: Ideal=%d bytes (%.2f%%) Actual=%d bytes (%.2f%%) "
               "Original = %d bytes\n",
               (int)ceil(tot_entropy/8),
               100.0*(tot_entropy/8)/(float)size,
               tot_msg,
               100.0*tot_msg/(float)size, size);

    }

    if (!(f = fopen(argv[2], "wb")))
        err(1, NULL);
    if (fwrite(out, 1, out_nr, f) != out_nr)
        err(1, NULL);
    fclose(f);

    return 0;
}
