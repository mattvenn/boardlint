"""Builds a Verilog testbench from the board's netlist and runs it with Icarus Verilog.

Every net becomes a wire.  Supply rails are supply1, grounds supply0, a net with a pull-up
resistor gets a `pullup`, nets joined through series resistors are one wire.  Parts whose model
has a `sim:` (or `serial_led:`) section are instantiated with their pins on those wires; the
testbench plays the MCU.  What the simulation proves is that the *wiring* lets the bus work:
straps, supplies, mode pins, pull-ups and chain order, as built.
"""
from __future__ import annotations
import os
import re
import shutil
import subprocess
import tempfile
from ..classify import signal_group, pulls
from ..power import _pins_named

VDIR = os.path.join(os.path.dirname(__file__), 'verilog')


def available():
    return shutil.which('iverilog') is not None and shutil.which('vvp') is not None


class Wires:
    def __init__(self, d):
        self.d = d
        self.canon = {}
        self.decl = {}
        self.n_float = 0

    def of_net(self, net_name):
        d = self.d
        if net_name is None:
            self.n_float += 1
            nm = f"nc_{self.n_float}"
            self.decl[nm] = f"wire {nm};"
            return nm
        if net_name not in self.canon:
            n = d.nets[net_name]
            if n.is_ground:
                nm, group = 'gnd_' + _ident(net_name), {net_name}
                self.decl[nm] = f"supply0 {nm};"
            elif n.is_power:
                nm, group = 'pwr_' + _ident(net_name), {net_name}
                self.decl[nm] = f"supply1 {nm};"
            else:
                group, _ = signal_group(d, net_name)
                nm = 'n_' + _ident(sorted(group)[0])
                ups, downs = pulls(d, net_name)
                self.decl[nm] = f"wire {nm};" + (f" pullup({nm});" if ups else '') + (f" pulldown({nm});" if downs and not ups else '')
            for g in group:
                self.canon[g] = nm
        return self.canon[net_name]

    def of_pin(self, pin):
        return self.of_net(pin.net if pin is not None else None)


def _ident(s):
    return re.sub(r'[^A-Za-z0-9_]', '_', s)


def _powered(d, w, c):
    sup = [w.of_pin(p) for p in c.pins.values()
           if p.net and d.nets[p.net].is_power and (p.etype == 'power_in' or p.role == 'power_in')]
    gnd = [w.of_pin(p) for p in c.pins.values() if p.net and d.nets[p.net].is_ground]
    floating = [p for p in c.pins.values() if (p.etype == 'power_in' or p.role in ('power_in', 'gnd')) and not p.net]
    terms = [f"({s} === 1'b1)" for s in sorted(set(sup))] + [f"({g} === 1'b0)" for g in sorted(set(gnd))]
    if floating or not sup or not gnd:
        terms.append("1'b0")
    return ' && '.join(terms)


def _run(tb: str, keep_as=None):
    wd = tempfile.mkdtemp(prefix='boardlint-vlog-')
    path = os.path.join(wd, 'tb.v')
    with open(path, 'w') as f:
        f.write(tb)
    if keep_as:
        os.makedirs(os.path.dirname(os.path.abspath(keep_as)), exist_ok=True)
        shutil.copy(path, keep_as)
    srcs = [os.path.join(VDIR, f) for f in sorted(os.listdir(VDIR)) if f.endswith('.v')]
    c = subprocess.run(['iverilog', '-g2005', '-o', os.path.join(wd, 'tb.vvp'), path, *srcs], capture_output=True, text=True)
    if c.returncode != 0:
        shutil.rmtree(wd, ignore_errors=True)
        return None, c.stderr
    r = subprocess.run(['vvp', '-n', os.path.join(wd, 'tb.vvp')], capture_output=True, text=True, timeout=120, cwd=wd)
    shutil.rmtree(wd, ignore_errors=True)
    return [l.split() for l in r.stdout.splitlines() if l.startswith('RESULT ')], r.stdout + r.stderr


# ----------------------------------------------------------------------------- I2C
def i2c_testbench(d, bus, addr_of):
    """bus: entry from checks.buses.i2c_buses; addr_of(component) -> statically resolved address or None."""
    w = Wires(d)
    scl = w.of_net(sorted(bus['scl'])[0])
    sda = w.of_net(sorted(bus['sda'])[0])
    inst, targets = [], []
    for ref in sorted(bus['devices']):
        c = d.components[ref]
        sim = (c.model or {}).get('sim') or {}
        if sim.get('model') != 'i2c_target':
            continue
        spin, kpin = bus['devices'][ref]
        m = c.model.get('i2c') or {}
        ab = m.get('address_bits')
        if ab:
            bits = [f"1'b{(int(ab.get('base', 0)) >> i) & 1}" for i in range(7)]
            for b in ab.get('pins') or []:
                pin = (_pins_named(c, b.get('pin')) or [None])[0]
                if pin is not None and pin.net:
                    bits[int(b.get('bit', 0))] = w.of_pin(pin)
                elif b.get('default') is not None:
                    bits[int(b.get('bit', 0))] = f"1'b{int(b['default'])}"
                else:
                    bits[int(b.get('bit', 0))] = "1'bz"
            addr = '{' + ', '.join(reversed(bits)) + '}'
        else:
            a = addr_of(c)
            addr = f"7'h{a:02x}" if a is not None else "7'bx"
        en = []
        for e in sim.get('enable') or []:
            pin = (_pins_named(c, e.get('pin')) or [None])[0]
            en.append(f"({w.of_pin(pin)} === 1'b{int(e.get('level', 1))})")
        prm = sim.get('params') or {}
        u = 'u_' + _ident(ref)
        inst.append(f"  i2c_target #(.ID_REG(8'h{int(prm.get('ID_REG', 0)):02x}), .ID_VAL(8'h{int(prm.get('ID_VAL', 0)):02x})) {u} "
                    f"(.scl({w.of_pin(kpin)}), .sda({w.of_pin(spin)}), .addr({addr}), "
                    f".enable({' && '.join(en) or chr(39).join(['1', 'b1'])}), .powered({_powered(d, w, c)}));")
        targets.append((ref, u, int(prm.get('ID_REG', 0)), int(prm.get('ID_VAL', 0))))
    if not targets:
        return None, []
    T = 2500
    L = ["`timescale 1ns/1ps", "module tb;"] + ['  ' + s for s in w.decl.values()] + inst + [
        "  reg scl_oe = 0, sda_oe = 0;",
        f"  assign {scl} = scl_oe ? 1'b0 : 1'bz;",
        f"  assign {sda} = sda_oe ? 1'b0 : 1'bz;",
        "  reg ack; reg [7:0] rd; integer a, i, nsel;",
        f"  task t_start; begin sda_oe = 0; #{T}; scl_oe = 0; #{T}; sda_oe = 1; #{T}; scl_oe = 1; #{T}; end endtask",
        f"  task t_stop; begin sda_oe = 1; #{T}; scl_oe = 0; #{T}; sda_oe = 0; #{T}; end endtask",
        "  task t_wr(input [7:0] b); begin",
        f"    for (i = 7; i >= 0; i = i - 1) begin sda_oe = ~b[i]; #{T}; scl_oe = 0; #{T}; scl_oe = 1; #{T}; end",
        f"    sda_oe = 0; #{T}; scl_oe = 0; #{T}; ack = ({sda} === 1'b0); scl_oe = 1; #{T};",
        "  end endtask",
        "  task t_rd(input nack); begin rd = 0;",
        f"    for (i = 7; i >= 0; i = i - 1) begin sda_oe = 0; #{T}; scl_oe = 0; #{T}; rd[i] = {sda}; scl_oe = 1; #{T}; end",
        f"    sda_oe = ~nack; #{T}; scl_oe = 0; #{T}; scl_oe = 1; #{T}; sda_oe = 0;",
        "  end endtask",
        "  initial begin",
        f"    #{4 * T};",
        f"    $display(\"RESULT idle scl=%b sda=%b\", {scl}, {sda});",
        "    for (a = 8; a < 120; a = a + 1) begin",
        "      t_start; t_wr({a[6:0], 1'b0});",
        "      nsel = " + ' + '.join(f"{u}.matched" for _, u, _, _ in targets) + ";",
        "      if (ack) $display(\"RESULT ack %0d %0d\", a, nsel);",
        "      t_stop;",
        "    end"]
    for ref, u, reg, val in targets:
        L += ["    for (a = 8; a < 120; a = a + 1) begin",
              "      t_start; t_wr({a[6:0], 1'b0});",
              f"      if (ack && {u}.matched) begin",
              f"        t_wr(8'h{reg:02x}); t_start; t_wr({{a[6:0], 1'b1}}); t_rd(1'b1);",
              f"        $display(\"RESULT id {ref} %0d %b %0d\", a, rd, 8'h{val:02x});",
              "      end",
              "      t_stop;",
              "    end"]
    L += ["    $finish;", "  end", "endmodule"]
    return '\n'.join(L) + '\n', targets


# ----------------------------------------------------------------------------- LED chains
def led_testbench(d, leds, heads, level_ok):
    """leds: ref -> (din pin, dout pin); heads: {driver net name: [refs]}; level_ok: ref -> bool."""
    w = Wires(d)
    inst = []
    for ref, (din, dout) in sorted(leds.items()):
        c = d.components[ref]
        vdd = [p for p in c.pins.values() if p.net and d.nets[p.net].is_power]
        gnd = [p for p in c.pins.values() if p.net and d.nets[p.net].is_ground]
        inst.append(f"  serial_led #(.LEVEL_OK({1 if level_ok.get(ref, True) else 0})) u_{_ident(ref)} "
                    f"(.din({w.of_pin(din)}), .dout({w.of_pin(dout) if dout is not None else ''}), "
                    f".vdd({w.of_pin(vdd[0]) if vdd else chr(39).join(['1', 'bz'])}), "
                    f".gnd({w.of_pin(gnd[0]) if gnd else chr(39).join(['1', 'bz'])}));")
    hw = sorted({w.of_net(h) for h in heads})
    n = len(leds) + 2
    L = ["`timescale 1ns/1ps", "module tb;"] + ['  ' + s for s in w.decl.values()] + inst
    for i, h in enumerate(hw):
        L += [f"  reg h{i}_en = 0, h{i}_v = 0;", f"  assign {h} = h{i}_en ? h{i}_v : 1'bz;"]
    L += ["  integer k, b; reg [23:0] word;", "  initial begin", "    #1000;"]
    for i, h in enumerate(hw):
        L += [f"    h{i}_en = 1; h{i}_v = 0; #100000;",
              f"    for (k = 1; k <= {n}; k = k + 1) begin word = k;",
              "      for (b = 23; b >= 0; b = b - 1) begin",
              f"        h{i}_v = 1; if (word[b]) #800; else #300;",
              f"        h{i}_v = 0; if (word[b]) #450; else #950;",
              "      end",
              "    end",
              "    #200000;"]
    for ref in sorted(leds):
        u = 'u_' + _ident(ref)
        L.append(f"    $display(\"RESULT led {ref} %b %0d\", {u}.got, {u}.grb);")
    L += ["    $finish;", "  end", "endmodule"]
    return '\n'.join(L) + '\n'
