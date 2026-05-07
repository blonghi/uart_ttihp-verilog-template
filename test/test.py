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


async def wait_for_tx_idle_high(dut, cycles):
    for _ in range(cycles):
        assert get_tx_pin(dut) == 1, "TX must remain high during idle"
        await RisingEdge(dut.clk)


async def wait_for_rx_valid_rise(dut, timeout_cycles=200000):
    prev = int(dut.dut.rx_valid.value)
    for _ in range(timeout_cycles):
        cur = int(dut.dut.rx_valid.value)
        if prev == 0 and cur == 1:
            return
        prev = cur
        await RisingEdge(dut.clk)
    assert False, "Timeout waiting for rx_valid rising edge"


async def sample_tx_frame_bits(dut):
    await wait_for_tx_start(dut)
    await ClockCycles(dut.clk, TX_BAUD_CYCLES + (TX_BAUD_CYCLES // 2))
    bits = []
    for _ in range(8):
        bits.append(get_tx_pin(dut))
        await ClockCycles(dut.clk, TX_BAUD_CYCLES)
    stop_bit = get_tx_pin(dut)
    return bits, stop_bit


def bits_lsb_first(byte_val):
    return [(byte_val >> i) & 0x1 for i in range(8)]


async def drive_and_wait_tx(dut, byte_val):
    await send_uart_frame_on_ui0(dut, byte_val)
    await wait_for_rx_valid(dut)
    bits, stop_bit = await sample_tx_frame_bits(dut)
    return bits, stop_bit


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


@cocotb.test()
async def test_rx_idle_does_not_false_trigger(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    set_rx_pin(dut, 1)
    for _ in range(RX_BAUD_CYCLES * 20):
        assert int(dut.dut.rx_valid.value) == 0, "rx_valid must stay low when RX line is idle high"
        await RisingEdge(dut.clk)


@cocotb.test()
async def test_tx_stays_high_while_idle(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    await wait_for_tx_idle_high(dut, TX_BAUD_CYCLES * 5)


@cocotb.test()
async def test_bit_order_lsb_first_0x55(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    bits, stop_bit = await drive_and_wait_tx(dut, 0x55)
    assert bits == bits_lsb_first(0x55), f"Expected LSB-first 0x55 bits, got {bits}"
    assert stop_bit == 1, "Stop bit must be high"


@cocotb.test()
async def test_pattern_0x00_frame(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    bits, stop_bit = await drive_and_wait_tx(dut, 0x00)
    assert bits == bits_lsb_first(0x00), f"Expected all-zero payload, got {bits}"
    assert stop_bit == 1, "Stop bit must be high"


@cocotb.test()
async def test_pattern_0xff_frame(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    bits, stop_bit = await drive_and_wait_tx(dut, 0xFF)
    assert bits == bits_lsb_first(0xFF), f"Expected all-one payload, got {bits}"
    assert stop_bit == 1, "Stop bit must be high"


@cocotb.test()
async def test_pattern_0xaa_frame(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    bits, stop_bit = await drive_and_wait_tx(dut, 0xAA)
    assert bits == bits_lsb_first(0xAA), f"Expected 0xAA payload bits, got {bits}"
    assert stop_bit == 1, "Stop bit must be high"


@cocotb.test()
async def test_pattern_0x3c_frame(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    bits, stop_bit = await drive_and_wait_tx(dut, 0x3C)
    assert bits == bits_lsb_first(0x3C), f"Expected 0x3C payload bits, got {bits}"
    assert stop_bit == 1, "Stop bit must be high"


@cocotb.test()
async def test_back_to_back_frames(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    patterns = [0x12, 0x34, 0x56]
    for byte_val in patterns:
        bits, stop_bit = await drive_and_wait_tx(dut, byte_val)
        assert bits == bits_lsb_first(byte_val), f"TX payload mismatch for {byte_val:#04x}"
        assert stop_bit == 1, "Stop bit must be high between frames"


@cocotb.test()
async def test_start_bit_detection_requires_low(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    set_rx_pin(dut, 1)
    await ClockCycles(dut.clk, RX_BAUD_CYCLES * 4)
    assert int(dut.dut.rx_valid.value) == 0, "rx_valid must not assert without a low start bit"


@cocotb.test()
async def test_rx_valid_pulse_not_stuck_high(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    await send_uart_frame_on_ui0(dut, 0x5A)
    await wait_for_rx_valid_rise(dut)
    await ClockCycles(dut.clk, RX_BAUD_CYCLES * 3)
    assert int(dut.dut.rx_valid.value) == 0, "rx_valid should deassert after frame completion"


@cocotb.test()
async def test_reset_during_tx_forces_idle(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    await send_uart_frame_on_ui0(dut, 0x55)
    await wait_for_rx_valid(dut)
    await wait_for_tx_start(dut)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 2)
    assert get_tx_pin(dut) == 1, "TX must return high during reset"
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)
    assert get_tx_pin(dut) == 1, "TX must remain idle high after reset recovery"


@cocotb.test()
async def test_no_extra_tx_without_new_frame(dut):
    await setup_clock(dut)
    await reset_dut(dut)
    await send_uart_frame_on_ui0(dut, 0xA5)
    await wait_for_rx_valid(dut)
    await wait_for_tx_start(dut)
    await ClockCycles(dut.clk, TX_BAUD_CYCLES * 12)
    assert get_tx_pin(dut) == 1, "TX must return to idle after one frame"
    await wait_for_tx_idle_high(dut, TX_BAUD_CYCLES * 6)
