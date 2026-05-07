import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge


CLK_PERIOD_NS = 20
TX_BAUD_CYCLES = 5208
RX_BAUD_CYCLES = 325


async def setup_clock(dut):
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    cocotb.start_soon(clock.start())
    await RisingEdge(dut.clk)


async def reset_dut(dut):
    dut.ena.value = 1
    dut.uio_in.value = 0
    dut.ui_in.value = 1
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)


def set_rx_pin(dut, bit_val):
    cur = int(dut.ui_in.value)
    cur = (cur & ~0x1) | (bit_val & 0x1)
    dut.ui_in.value = cur


def get_tx_pin(dut):
    return int(dut.uo_out.value) & 0x1


async def send_uart_frame_on_ui0(dut, byte_val):
    set_rx_pin(dut, 1)
    await ClockCycles(dut.clk, RX_BAUD_CYCLES)

    set_rx_pin(dut, 0)
    await ClockCycles(dut.clk, RX_BAUD_CYCLES)

    for i in range(8):
        set_rx_pin(dut, (byte_val >> i) & 0x1)
        await ClockCycles(dut.clk, RX_BAUD_CYCLES)

    set_rx_pin(dut, 1)
    await ClockCycles(dut.clk, RX_BAUD_CYCLES)


async def wait_for_rx_valid(dut, timeout_cycles=200000):
    for _ in range(timeout_cycles):
        if int(dut.dut.rx_valid.value) == 1:
            return
        await RisingEdge(dut.clk)
    assert False, "Timeout waiting for rx_valid"


async def wait_for_tx_start(dut, timeout_cycles=200000):
    for _ in range(timeout_cycles):
        if get_tx_pin(dut) == 0:
            return
        await RisingEdge(dut.clk)
    assert False, "Timeout waiting for TX start bit on uo_out[0]"


@cocotb.test()
async def test_tx_idle_high_after_reset(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    assert get_tx_pin(dut) == 1


@cocotb.test()
async def test_rx_valid_after_serial_frame(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    await send_uart_frame_on_ui0(dut, 0x55)
    await wait_for_rx_valid(dut)


@cocotb.test()
async def test_tx_starts_after_rx_valid(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    await send_uart_frame_on_ui0(dut, 0x55)
    await wait_for_rx_valid(dut)
    await wait_for_tx_start(dut)
