#!/usr/bin/env python2
# coding: utf-8
# /usr/lib/cups/filter/pstohpgl.py

"""
http://www.cups.org/doc-1.1/spm.html#4_1
"""

import re
from os import environ, stat
from itertools import islice, izip
from sys import argv, exit,stderr, stdin, stdout
from subprocess import Popen,PIPE


def alert(msg):
    stderr.write('ALERT: %s\n' % msg)
    stderr.flush()


def counting_cat(fname, percent=True):
    CHUNKSIZE = 4096
    ll = 0
    f = open(fname)
    size = stat(fname).st_size

    while 1:
        chunk = f.read(CHUNKSIZE)
        if not chunk:
            break
        stdout.write(chunk)
        ll += len(chunk)
        if percent and size:
            alert('%3.1f%% spooled' % (100 * float(ll) / size))
        else:
            alert('%s/%s spooled' % (ll, size))


def shifthpgl(hpgl_prog, xoff, yoff):
    def group_pairs(l):
        pairs = izip(islice(l, 0, len(l), 2), islice(l, 1, len(l), 2))
        return pairs

    def handle_statement(statement):
        if not statement:
            return

        cmd = statement[:2]
        if cmd.upper() in ('EA', 'RA', 'PA', 'PD', 'PU', 'IP'):
            coord_list = statement[2:].split(',')
            coord_pairs = group_pairs(coord_list)
            res = []
            for x, y in coord_pairs:
                try:
                    res.append(str(int(x) + xoff))
                    res.append(str(int(y) + yoff))
                except Exception, e:
                    raise ValueError('Problems with this statement: ' + statement)
            return cmd + ','.join(res)
        elif cmd.upper() in ('PG', ):
            return statement
        else:
            return statement

    res = []
    for l in hpgl_prog.split('\n'):
        l = l.strip()
        for l_line in l.split(';'):
            if l_line:
                res.append(handle_statement(l_line))
    return ';'.join(res) + ';\n'


def pstohpgl(src, dest, xscale, yscale):
    proc = Popen(args=['pstoedit', '-nc', '-flat', '0.1', '-xscale', str(xscale), '-yscale', str(yscale), '-f', 'plot-hpgl', src, dest],
                 stdout=PIPE,
                 stderr=PIPE,
                 close_fds=True)
    sout, serr = proc.communicate()
#    if proc.returncode != 0:
#        alert(sout + serr, 'ERROR')
#        raise RuntimeError('pstoedit failed.')


def distill(src, dest):
    proc = Popen(args=['hpgl-distiller', '-i', src, '-o', dest], stdout=PIPE, stderr=PIPE, close_fds=True)
    sout, serr = proc.communicate()
#    if proc.returncode != 0:
#        alert(''.join(stdout.readlines() + stderr.readlines()), 'ERROR')
#        raise RuntimeError('distiller failed.')


def hpgl_info(fname, logname=None):
    proc = Popen(args = ['hp2xx', '-N', '-t', '-f-', '-m', 'hpgl'], stdin=PIPE, stdout=PIPE, stderr=PIPE)

    sout,report = proc.communicate(open(fname).read())
    logname = fname + '.report'
    if logname:
        open(logname, 'w').write(report)
    # Width  x  height: 205.55 x 195.70 mm, true sizes
    # Coordinate range: (2156, 1320) ... (10378, 9148)
    size_m = re.search(r'Width\W*x\W*height: ([-0-9.]*)\W*x\W*([-0-9.]*) mm', report)
    if not size_m:
        raise RuntimeError('hp2xx failed (1)')
    width, height = [float(x) for x in size_m.groups()]
    coord_m = re.search(r'Coordinate range:\W*\(([-0-9.]*)\W*,\W*([-0-9.]*)\)\W*\.\.\.', report)
    if not coord_m:
        raise RuntimeError('hp2xx failed (2)')
    xoff, yoff = [int(x) for x in coord_m.groups()]
    return {'size': (width, height), 'offset': (xoff, yoff)}


if __name__ == '__main__':
    try:
        job, user, title, copies, options, filename = argv[1:]
    except ValueError:
        job, user, title, copies, options = argv[1:]
        filename = '-'
    alert('Starting Filter...')
    if filename == '-':
        src = '%s/cutter.%s.ps' % (environ.get('TMP', '/tmp'), job)
        open(src, 'w').write(stdin.read())
    else:
        src = filename
    hpgl = '%s/cutter.%s.hpgl' % (environ.get('TMP', '/tmp'), job)
    alert('PS -> HPGL')
    pstohpgl(src, hpgl, xscale='1.1187', yscale='1.1187')
    distilled = hpgl + '.distilled'
    shifted = hpgl + '.shifted'
    alert('Distilling...')
    distill(hpgl, distilled)
    info = hpgl_info(distilled)
    xoff, yoff = info['offset']
    alert('Size %sx%s mm' % info['size'])
    alert('Shifting by %s, %s' % (xoff, yoff))
    shifted_proc = shifthpgl(open(distilled).read(), -xoff, -yoff)
    open(shifted, 'w').write(shifted_proc)
    alert('Printing %s bytes of data' % len(shifted_proc))
    counting_cat(shifted, len(shifted_proc))
    alert('Finished spooling')
