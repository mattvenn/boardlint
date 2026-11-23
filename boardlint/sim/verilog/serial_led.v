// Behavioural single-wire addressable LED (WS2812 / SK6812 family) for chain simulation.
// Decodes bits by high time, keeps the first 24 after a reset, forwards the rest on DOUT.
// LEVEL_OK = 0 models a data input that never reaches its logic-high threshold.
`timescale 1ns/1ps
module serial_led #(
    parameter LEVEL_OK = 1,
    parameter T_THRESHOLD_NS = 550,     // shorter high = 0, longer = 1
    parameter T_RESET_NS = 80000
) (
    input  wire din,
    output wire dout,
    input  wire vdd,
    input  wire gnd
);
    wire ok = (vdd === 1'b1) && (gnd === 1'b0) && (LEVEL_OK != 0);
    wire d  = ok ? din : 1'bx;
    reg [23:0] grb = 0;
    reg        got = 0, pass = 0;
    integer    n = 0;
    time       t_rise = 0, t_last = 0;
    assign dout = ok ? ((pass && d === 1'b1) ? 1'b1 : 1'b0) : 1'bz;

    always @(d) t_last = $time;
    always @(posedge d) if (d === 1'b1) t_rise = $time;
    always @(negedge d) if (d === 1'b0 && t_rise != 0) begin
        if (n < 24) begin
            grb = {grb[22:0], ($time - t_rise) > T_THRESHOLD_NS};
            n = n + 1;
            if (n == 24) begin got = 1; pass = 1; end
        end
    end
    always #10000 if (d === 1'b0 && ($time - t_last) > T_RESET_NS && n != 0) begin
        pass = 0; n = 0;
    end
endmodule
