// Behavioural I2C target for board-level connectivity simulation (4-state, for Icarus Verilog).
// Not a model of any one chip: it answers at `addr`, keeps a register pointer, and returns ID_VAL
// when ID_REG is read.  `addr`, `enable` and `powered` come from the board's own wiring, so a wrong
// strap, a missing supply or a mode pin at the wrong level shows up as "no answer".
`timescale 1ns/1ps
module i2c_target #(
    parameter [7:0] ID_REG = 8'h0F,
    parameter [7:0] ID_VAL = 8'h33
) (
    input  wire       scl,
    inout  wire       sda,
    input  wire [6:0] addr,
    input  wire       enable,
    input  wire       powered
);
    localparam IDLE = 0, ADDR = 1, WR = 2, RD = 3;
    reg       sda_low = 0;
    reg [1:0] state = IDLE;
    reg [3:0] bitcnt = 0;
    reg [7:0] sh = 0, ptr = 0, data = 0;
    reg       rw = 0, after_ack = 0, nacked = 0, first_wr = 0;
    reg       matched = 0;              // high while this target is the one addressed
    wire      alive = (powered === 1'b1) && (enable === 1'b1);
    assign sda = (sda_low && alive) ? 1'b0 : 1'bz;

    always @(negedge sda) if (scl === 1'b1 && alive) begin          // START
        state = ADDR; bitcnt = 0; sda_low = 0; after_ack = 0; matched = 0;
    end
    always @(posedge sda) if (scl === 1'b1 && sda === 1'b1) begin   // STOP
        state = IDLE; sda_low = 0; matched = 0; after_ack = 0;
    end
    always @(posedge scl) if (scl === 1'b1 && state != IDLE) begin
        if (bitcnt < 8) begin
            sh = {sh[6:0], sda === 1'b1};
            bitcnt = bitcnt + 1;
        end else begin
            nacked = (sda !== 1'b0);
            after_ack = 1;
            bitcnt = 0;
        end
    end
    always @(negedge scl) if (scl === 1'b0 && state != IDLE) begin
        if (after_ack) begin
            after_ack = 0;
            sda_low = 0;
            if (state == ADDR) begin state = rw ? RD : WR; first_wr = 1; end
            else if (state == RD && nacked) state = IDLE;
            if (state == RD) begin
                data = (ptr == ID_REG) ? ID_VAL : 8'h00;
                ptr = ptr + 1;
                sda_low = ~data[7];
            end
        end else if (bitcnt == 8) begin
            if (state == ADDR) begin
                if (sh[7:1] === addr) begin rw = sh[0]; sda_low = 1; matched = 1; end
                else state = IDLE;
            end else if (state == WR) begin
                if (first_wr) begin ptr = sh; first_wr = 0; end
                sda_low = 1;
            end else sda_low = 0;                                   // RD: release for the controller's ACK
        end else if (state == RD) begin
            sda_low = ~data[7 - bitcnt];
        end
    end
endmodule
