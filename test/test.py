"""Cocotb tests for the current UART RTL exactly as written.

Known RTL issues discovered during repository review:
1) In src/baud_rate_gen.v, both counters reset when rst_n == 1 (polarity bug).
2) In src/receiver.v STOP state, rx_valid is set to 1 and then immediately set to 0.
3) In src/project.v, transmitter output is internal (wire rx) and not mapped to uo_out bit.
4) src/project.v implements an internal UART loop: ui_in loads transmitter data directly.

Because of (2), loopback through receiver->rx_valid->transmitter is expected to fail until RTL is fixed.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge

try:
    from cocotb.result import TestFailure
except ImportError:  # cocotb v2 favors plain assertions; keep compatibility
    TestFailure = AssertionError


# 50MHz clock from info.yaml -> period = 1 / 50_000_000 s = 20 ns
CLK_PERIOD_NS = 20
# tx_counter compares against 5208 in baud_rate_gen.v -> 50_000_000 / 5208 ~= 9600 baud
TX_BAUD_CYCLES = 5208
# rx_counter compares against 325 in baud_rate_gen.v -> 50_000_000 / 325 ~= 153846 sample ticks
RX_BAUD_CYCLES = 325

# From source review:
# - No uo_out bit is wired to transmitter.tx in project.v (TX is internal only).
TX_UO_BIT = None


async def setup_clock(dut):
    """Start the simulation clock on dut.clk using the period derived from info.yaml.

    In cocotb, time only advances when you explicitly create/schedule clock toggles.
    We launch clock.start() as a background coroutine so tests can continue driving/checking
    signals while the clock keeps running in parallel.
    """
    # Build a repeating square-wave clock with 20ns period (50MHz).
    clock = Clock(dut.clk, CLK_PERIOD_NS, unit="ns")
    # start_soon schedules the clock coroutine concurrently; it does not block this function.
    cocotb.start_soon(clock.start())
    # Wait one edge so downstream code sees a started/stable clock.
    await RisingEdge(dut.clk)


async def reset_dut(dut):
    """Apply active-low reset and initialize top-level inputs to safe idle values.

    rst_n is active-low: 0 means reset asserted, 1 means normal operation.
    We hold reset for 5 cycles so all sequential logic has multiple edges to settle.
    """
    # Enable design selection and clear non-UART inputs.
    dut.ena.value = 1
    dut.uio_in.value = 0

    # ui_in is the parallel byte source loaded into the transmitter in project.v.
    dut.ui_in.value = 0

    # Assert reset low for 5 full cycles.
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)

    # Release reset to begin normal operation.
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)


async def start_internal_loopback(dut, byte_val):
    """Kick off one internal loopback transfer by loading ui_in.

    In this RTL, ui_in is wired to tx_data and transmitter starts when wr_enb (rx_valid) pulses.
    """
    # Load the byte that transmitter will serialize.
    dut.ui_in.value = byte_val & 0xFF
    # Give sequential logic a couple cycles to capture and progress.
    await ClockCycles(dut.clk, 2)


def get_tx_line(dut):
    """Read the UART TX line and return it as an integer bit (0 or 1).

    Requested behavior is to extract TX from uo_out[bit], but current RTL has no TX mapping there.
    So this reads the internal transmitter output directly.
    """
    # If top-level TX mapping is added later, replace with uo_out[TX_UO_BIT].
    return int(dut.dut.u_transmitter.tx.value)


async def uart_recv_byte(dut, timeout_cycles=200000):
    """Wait for TX start bit and reconstruct one UART byte by center sampling.

    Center sampling is used because bit edges may have small timing error/jitter.
    Sampling near the middle of each bit window is more robust than sampling at edges.
    """
    # Wait for start bit (transition to LOW) with timeout protection.
    for _ in range(timeout_cycles):
        if get_tx_line(dut) == 0:
            break
        await RisingEdge(dut.clk)
    else:
        raise TestFailure(
            f"Timeout waiting for TX start bit after {timeout_cycles} cycles. "
            "Likely no wr_enb/rx_valid handoff to transmitter."
        )

    # Move to center of first data bit:
    # - We are currently at/near start bit observation point.
    # - Wait 1.5 bit-times total to land in b0 center.
    await ClockCycles(dut.clk, TX_BAUD_CYCLES + (TX_BAUD_CYCLES // 2))

    recv_val = 0
    for bit_index in range(8):
        sampled = get_tx_line(dut)
        recv_val |= (sampled << bit_index)
        await ClockCycles(dut.clk, TX_BAUD_CYCLES)

    return recv_val


async def uart_loopback(dut, byte_val):
    """Load ui_in and receive one serialized byte from transmitter TX."""
    await start_internal_loopback(dut, byte_val)
    return await uart_recv_byte(dut)


@cocotb.test()
async def test_reset_output_is_zero(dut):
    """Verify uo_out is 0x00 immediately after reset release."""
    await setup_clock(dut)
    await reset_dut(dut)

    # If this fails, receiver output register is not reset to a known zero value.
    assert int(dut.uo_out.value) == 0x00


@cocotb.test()
async def test_tx_idle_high(dut):
    """Verify TX line is high (idle state) right after reset."""
    await setup_clock(dut)
    await reset_dut(dut)

    # If this fails, transmitter is not holding UART idle level high.
    assert get_tx_line(dut) == 1


@cocotb.test()
async def test_loopback_0x55(dut):
    """Send 0x55 and verify the echoed byte is 0x55."""
    await setup_clock(dut)
    await reset_dut(dut)

    # Known RTL blocker: receiver rx_valid does not pulse high in current code,
    # so transmitter never gets wr_enb and cannot start a frame.
    recv = await uart_loopback(dut, 0x55)
    # If this fails after RTL fix, timing/state handling is wrong for alternating bits.
    assert recv == 0x55


@cocotb.test()
async def test_loopback_0x00(dut):
    """Send 0x00 and verify the echoed byte is 0x00."""
    await setup_clock(dut)
    await reset_dut(dut)

    # If this fails after RTL fix, long-low data pattern handling is broken.
    recv = await uart_loopback(dut, 0x00)
    assert recv == 0x00


@cocotb.test()
async def test_loopback_0xFF(dut):
    """Send 0xFF and verify the echoed byte is 0xFF."""
    await setup_clock(dut)
    await reset_dut(dut)

    # If this fails after RTL fix, long-high data pattern handling is broken.
    recv = await uart_loopback(dut, 0xFF)
    assert recv == 0xFF


@cocotb.test()
async def test_loopback_0xAA(dut):
    """Send 0xAA and verify the echoed byte is 0xAA."""
    await setup_clock(dut)
    await reset_dut(dut)

    # If this fails after RTL fix, alternating pattern (inverse of 0x55) is not sampled correctly.
    recv = await uart_loopback(dut, 0xAA)
    assert recv == 0xAA


@cocotb.test()
async def test_loopback_sequential_bytes(dut):
    """Send multiple bytes in sequence and verify each echoed byte matches."""
    await setup_clock(dut)
    await reset_dut(dut)

    for value in [0x01, 0x02, 0x04, 0x08]:
        recv = await uart_loopback(dut, value)
        # If this fails after RTL fix, FSM recovery between frames is broken.
        assert recv == value
        # One-bit-time idle gap between frames.
        await ClockCycles(dut.clk, TX_BAUD_CYCLES)


@cocotb.test()
async def test_rx_valid_clears_between_frames(dut):
    """Send same byte twice and verify two distinct successful echoes."""
    await setup_clock(dut)
    await reset_dut(dut)

    recv_1 = await uart_loopback(dut, 0xA5)
    recv_2 = await uart_loopback(dut, 0xA5)
    # If this fails after RTL fix, rx_valid may be stuck or frame boundaries are not respected.
    assert recv_1 == 0xA5 and recv_2 == 0xA5


@cocotb.test()
async def test_no_output_during_receive(dut):
    """Verify TX does not start changing during mid-receive before valid handoff."""
    await setup_clock(dut)
    await reset_dut(dut)

    # Start internal transfer and inspect TX while receiver/transmitter progress.
    tx_before = get_tx_line(dut)
    send_task = cocotb.start_soon(start_internal_loopback(dut, 0x3C))
    await ClockCycles(dut.clk, TX_BAUD_CYCLES * 4)
    tx_mid = get_tx_line(dut)
    await send_task

    # If this fails after RTL fix, TX may be launching too early (before receiver completes).
    assert tx_mid == tx_before


@cocotb.test()
async def test_stop_bit_respected(dut):
    """Verify TX returns high for stop/idle after a valid frame."""
    await setup_clock(dut)
    await reset_dut(dut)

    _ = await uart_loopback(dut, 0x5A)
    await ClockCycles(dut.clk, TX_BAUD_CYCLES)
    # If this fails after RTL fix, STOP state/line-idle behavior is incorrect.
    assert get_tx_line(dut) == 1
