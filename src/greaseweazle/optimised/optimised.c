
#define PY_SSIZE_T_CLEAN
#include "Python.h"
#include <stdio.h>
#include <stdint.h>
#include "mac.h"
#include "c64.h"
#include "apple2.h"
#include "apple_gcr_6a2.h"

#define FLUXOP_INDEX   1
#define FLUXOP_SPACE   2
#define FLUXOP_ASTABLE 3

/* bitarray.append(value) */
static PyObject *append_s;
static int bitarray_append(PyObject *bitarray, PyObject *value)
{
    PyObject *res = PyObject_CallMethodObjArgs(
        bitarray, append_s, value, NULL);
    if (res == NULL)
        return 0;
    Py_DECREF(res);
    return 1;
}

/* Like PyList_Append() but steals a reference to @item. */
static int PyList_Append_SR(PyObject *list, PyObject *item)
{
    int rc = PyList_Append(list, item);
    Py_DECREF(item);
    return rc;
}

static PyObject *
flux_to_bitcells(PyObject *self, PyObject *args)
{
    /* Parameters */
    PyObject *bit_array, *time_array, *revolutions;
    PyObject *index_iter, *flux_iter;
    double freq, clock_centre, clock_min, clock_max;
    double pll_period_adj, pll_phase_adj;

    /* Local variables */
    PyObject *item;
    double _clock, clock, new_ticks, ticks, to_index;
    int i, zeros, nbits;

    if (!PyArg_ParseTuple(args, "OOOOOdddddd",
                          &bit_array, &time_array, &revolutions,
                          &index_iter, &flux_iter,
                          &freq, &clock_centre, &clock_min, &clock_max,
                          &pll_period_adj, &pll_phase_adj))
        return NULL;

    nbits = 0;
    ticks = 0.0;
    clock = clock_centre;

    /* to_index = next(index_iter) */
    if ((item = PyIter_Next(index_iter)) == NULL)
        return NULL;
    to_index = PyFloat_AsDouble(item);
    Py_DECREF(item);
    if (PyErr_Occurred())
        return NULL;

    /* for x in flux_iter: */
    assert(PyIter_Check(flux_iter));
    while ((item = PyIter_Next(flux_iter)) != NULL) {

        double x = PyFloat_AsDouble(item);
        Py_DECREF(item);
        if (PyErr_Occurred())
            return NULL;

        /* Gather enough ticks to generate at least one bitcell. */
        ticks += x / freq;
        if (ticks < clock/2)
            continue;

        /* Clock out zero or more 0s, followed by a 1. */
        zeros = 0;
        for (;;) {
            ticks -= clock;
            if (ticks < clock/2)
                break;
            zeros += 1;
            if (!bitarray_append(bit_array, Py_False))
                return NULL;
        }
        if (!bitarray_append(bit_array, Py_True))
            return NULL;

        /* PLL: Adjust clock window position according to phase mismatch. */
        new_ticks = ticks * (1.0 - pll_phase_adj);

        /* Distribute the clock adjustment across all bits we just emitted. */
        _clock = clock + (ticks - new_ticks) / (zeros + 1);
        for (i = 0; i <= zeros; i++) {

            /* Check if we cross the index mark. */
            to_index -= _clock;
            if (to_index < 0) {
                if (PyList_Append_SR(revolutions, PyLong_FromLong(nbits)) < 0)
                    return NULL;
                nbits = 0;
                if ((item = PyIter_Next(index_iter)) == NULL)
                    return NULL;
                to_index += PyFloat_AsDouble(item);
                Py_DECREF(item);
                if (PyErr_Occurred())
                    return NULL;
            }

            /* Emit bit time. */
            nbits += 1;
            if (PyList_Append_SR(time_array, PyFloat_FromDouble(_clock)) < 0)
                return NULL;

        }

        /* PLL: Adjust clock frequency according to phase mismatch. */
        if (zeros <= 3) {
            /* In sync: adjust clock by a fraction of the phase mismatch. */
            clock += ticks * pll_period_adj;
        } else {
            /* Out of sync: adjust clock towards centre. */
            clock += (clock_centre - clock) * pll_period_adj;
        }
        /* Clamp the clock's adjustment range. */
        if (clock < clock_min)
            clock = clock_min;
        else if (clock > clock_max)
            clock = clock_max;

        ticks = new_ticks;

    }

    Py_RETURN_NONE;
}


static int _read_28bit(uint8_t *p)
{
    int x;
    x  = (p[0]       ) >>  1;
    x |= (p[1] & 0xfe) <<  6;
    x |= (p[2] & 0xfe) << 13;
    x |= (p[3] & 0xfe) << 20;
    return x;
}

static PyObject *
decode_flux(PyObject *self, PyObject *args)
{
    /* Parameters */
    Py_buffer bytearray;
    PyObject *res = NULL;

    /* bytearray buffer */
    uint8_t *p;
    Py_ssize_t l;

    /* Local variables */
    PyObject *flux, *index;
    long val, ticks, ticks_since_index;
    int i, opcode;

    if (!PyArg_ParseTuple(args, "y*", &bytearray))
        return NULL;
    p = bytearray.buf;
    l = bytearray.len;

    /* assert dat[-1] == 0 */
    if ((l == 0) || (p[l-1] != 0)) {
        PyErr_SetString(PyExc_ValueError, "Flux is not NUL-terminated");
        PyBuffer_Release(&bytearray);
        return NULL;
    }
    /* len(dat) -= 1 */
    l -= 1;

    /* flux, index = [], [] */
    flux = PyList_New(0);
    index = PyList_New(0);
    /* ticks, ticks_since_index = 0, 0 */
    ticks = 0;
    ticks_since_index = 0;

    while (l != 0) {
        i = *p++;
        if (i == 255) {
            if ((l -= 2) < 0)
                goto oos;
            opcode = *p++;
            switch (opcode) {
            case FLUXOP_INDEX:
                if ((l -= 4) < 0)
                    goto oos;
                val = _read_28bit(p);
                p += 4;
                if (PyList_Append_SR(
                        index, PyLong_FromLong(
                            ticks_since_index + ticks + val)) < 0)
                    goto out;
                ticks_since_index = -(ticks + val);
                break;
            case FLUXOP_SPACE:
                if ((l -= 4) < 0)
                    goto oos;
                ticks += _read_28bit(p);
                p += 4;
                break;
            default:
                PyErr_Format(PyExc_ValueError,
                             "Bad opcode in flux stream (%d)", opcode);
                goto out;
            }
        } else {
            if (i < 250) {
                l -= 1;
                val = i;
            } else {
                if ((l -= 2) < 0)
                    goto oos;
                val = 250 + (i - 250) * 255;
                val += *p++ - 1;
            }
            ticks += val;
            if (PyList_Append_SR(flux, PyLong_FromLong(ticks)) < 0)
                goto out;
            ticks_since_index += ticks;
            ticks = 0;
        }
    }

    res = Py_BuildValue("OO", flux, index);

out:
    PyBuffer_Release(&bytearray);
    Py_DECREF(flux);
    Py_DECREF(index);
    return res;

oos:
    PyErr_SetString(PyExc_ValueError, "Unexpected end of flux");
    goto out;
}

static PyObject *
py_decode_mac_gcr(PyObject *self, PyObject *args)
{
    Py_buffer in;
    PyObject *out = NULL;

    if (!PyArg_ParseTuple(args, "y*", &in))
        return NULL;

    out = PyBytes_FromStringAndSize(NULL, in.len);
    if (out == NULL)
        goto fail;

    apple_gcr_6a2_decode_bytes((const uint8_t *)in.buf,
                               (uint8_t *)PyBytes_AsString(out),
                               in.len);

fail:
    PyBuffer_Release(&in);
    return out;
}

static PyObject *
py_encode_mac_gcr(PyObject *self, PyObject *args)
{
    Py_buffer in;
    PyObject *out = NULL;

    if (!PyArg_ParseTuple(args, "y*", &in))
        return NULL;

    out = PyBytes_FromStringAndSize(NULL, in.len);
    if (out == NULL)
        goto fail;

    apple_gcr_6a2_encode_bytes((const uint8_t *)in.buf,
                               (uint8_t *)PyBytes_AsString(out),
                               in.len);

fail:
    PyBuffer_Release(&in);
    return out;
}

static PyObject *
py_decode_mac_sector(PyObject *self, PyObject *args)
{
    Py_buffer in;
    PyObject *out;
    int status;
    PyObject *res = NULL;

    if (!PyArg_ParseTuple(args, "y*", &in))
        return NULL;
    if (in.len < MAC_ENCODED_SECTOR_LENGTH)
        goto fail;

    out = PyBytes_FromStringAndSize(NULL, MAC_SECTOR_LENGTH);
    if (out == NULL)
        goto fail;

    status = decode_mac_sector((const uint8_t *)in.buf,
                               (uint8_t *)PyBytes_AsString(out));

    res = Py_BuildValue("Oi", out, status);

    Py_DECREF(out);
fail:
    PyBuffer_Release(&in);
    return res;
}

static PyObject *
py_encode_mac_sector(PyObject *self, PyObject *args)
{
    Py_buffer in;
    PyObject *out = NULL;

    if (!PyArg_ParseTuple(args, "y*", &in))
        return NULL;
    if (in.len < MAC_SECTOR_LENGTH)
        goto fail;

    out = PyBytes_FromStringAndSize(NULL, MAC_ENCODED_SECTOR_LENGTH);
    if (out == NULL)
        goto fail;

    encode_mac_sector((const uint8_t *)in.buf,
                      (uint8_t *)PyBytes_AsString(out));

fail:
    PyBuffer_Release(&in);
    return out;
}

static PyObject *
py_decode_c64_gcr(PyObject *self, PyObject *args)
{
    Py_buffer in;
    PyObject *out = NULL;
    int out_len;

    if (!PyArg_ParseTuple(args, "y*", &in))
        return NULL;

    if (in.len % 5)
        goto fail;
    out_len = (in.len / 5) * 4;

    out = PyBytes_FromStringAndSize(NULL, out_len);
    if (out == NULL)
        goto fail;

    decode_c64_gcr((const uint8_t *)in.buf,
                   (uint8_t *)PyBytes_AsString(out),
                   out_len);

fail:
    PyBuffer_Release(&in);
    return out;
}

static PyObject *
py_encode_c64_gcr(PyObject *self, PyObject *args)
{
    Py_buffer in;
    PyObject *out = NULL;
    int out_len;

    if (!PyArg_ParseTuple(args, "y*", &in))
        return NULL;

    if (in.len % 4)
        goto fail;
    out_len = (in.len / 4) * 5;

    out = PyBytes_FromStringAndSize(NULL, out_len);
    if (out == NULL)
        goto fail;

    encode_c64_gcr((const uint8_t *)in.buf,
                   (uint8_t *)PyBytes_AsString(out),
                   in.len);

fail:
    PyBuffer_Release(&in);
    return out;
}

static PyObject *
py_decode_apple2_sector(PyObject *self, PyObject *args)
{
    Py_buffer in;
    PyObject *out;
    int status;
    PyObject *res = NULL;

    if (!PyArg_ParseTuple(args, "y*", &in))
        return NULL;

    out = PyBytes_FromStringAndSize(NULL, APPLE2_SECTOR_LENGTH);
    if (out == NULL)
        goto fail;

    status = decode_apple2_sector((const uint8_t *)in.buf, in.len,
                                  (uint8_t *)PyBytes_AsString(out));

    res = Py_BuildValue("Oi", out, status);

    Py_DECREF(out);
fail:
    PyBuffer_Release(&in);
    return res;
}

static PyObject *
py_encode_apple2_sector(PyObject *self, PyObject *args)
{
    Py_buffer in;
    PyObject *out = NULL;

    if (!PyArg_ParseTuple(args, "y*", &in))
        return NULL;
    if (in.len < APPLE2_SECTOR_LENGTH)
        goto fail;

    out = PyBytes_FromStringAndSize(NULL, APPLE2_ENCODED_SECTOR_LENGTH+1);
    if (out == NULL)
        goto fail;

    encode_apple2_sector((const uint8_t *)in.buf,
                         (uint8_t *)PyBytes_AsString(out));

fail:
    PyBuffer_Release(&in);
    return out;
}

uint8_t *td0_unpack(uint8_t *packeddata, unsigned int size,
                    unsigned int *unpacked_size);

static PyObject *
py_td0_unpack(PyObject *self, PyObject *args)
{
    Py_buffer in;
    PyObject *out_obj = NULL;
    unsigned int out_len;
    uint8_t *out;

    if (!PyArg_ParseTuple(args, "y*", &in))
        return NULL;

    out = td0_unpack((uint8_t *)in.buf, in.len, &out_len);
    if (out == NULL)
        goto fail;

    out_obj = PyBytes_FromStringAndSize((char *)out, out_len);
    free(out);

fail:
    PyBuffer_Release(&in);
    return out_obj;
}

static PyMethodDef modulefuncs[] = {
    { "flux_to_bitcells", flux_to_bitcells, METH_VARARGS, NULL },
    { "decode_flux", decode_flux, METH_VARARGS, NULL },
    { "decode_mac_gcr", py_decode_mac_gcr, METH_VARARGS, NULL },
    { "encode_mac_gcr", py_encode_mac_gcr, METH_VARARGS, NULL },
    { "decode_mac_sector", py_decode_mac_sector, METH_VARARGS, NULL },
    { "encode_mac_sector", py_encode_mac_sector, METH_VARARGS, NULL },
    { "decode_c64_gcr", py_decode_c64_gcr, METH_VARARGS, NULL },
    { "encode_c64_gcr", py_encode_c64_gcr, METH_VARARGS, NULL },
    { "decode_apple2_sector", py_decode_apple2_sector, METH_VARARGS, NULL },
    { "encode_apple2_sector", py_encode_apple2_sector, METH_VARARGS, NULL },
    { "td0_unpack", py_td0_unpack, METH_VARARGS, NULL },
    { NULL }
};

static PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT, "optimised", 0, -1, modulefuncs,
};

PyMODINIT_FUNC PyInit_optimised(void)
{
    append_s = Py_BuildValue("s", "append");
    return PyModule_Create(&moduledef);
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
