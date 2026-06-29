import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge


CLK_PERIOD_NS = 20
TX_BAUD_CYCLES = 5208
RX_BAUD_CYCLES = 5208


# ---------------------------------------------------------------------------
# Infrastructure helpers
# ---------------------------------------------------------------------------

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


def set_wr_enb_pin(dut, bit_val):
    cur = int(dut.uio_in.value)
    cur = (cur & ~0x1) | (bit_val & 0x1)
    dut.uio_in.value = cur


async def issue_tx_write(dut, byte_val):
    assert (byte_val & 1) == 1, "TX byte must have LSB=1 (ui_in[0] RX idle)"
    dut.ui_in.value = byte_val
    set_wr_enb_pin(dut, 1)
    await RisingEdge(dut.clk)
    set_wr_enb_pin(dut, 0)
    await RisingEdge(dut.clk)


def get_tx_pin(dut):
    return int(dut.uo_out.value) & 0x1


def get_rx_data(dut):
    return int(dut.rx_data.value)


def get_rx_valid(dut):
    """Read rx_valid from top-level output bit uo_out[1]."""
    return (int(dut.uo_out.value) >> 1) & 0x1


def bits_lsb_first(byte_val):
    return [(byte_val >> i) & 0x1 for i in range(8)]


# ---------------------------------------------------------------------------
# RX stimulus helpers
# ---------------------------------------------------------------------------

async def send_uart_frame_on_ui0(dut, byte_val):
    """Drive a complete UART frame (idle→start→8 data→stop) onto ui_in[0]."""
    set_rx_pin(dut, 1)
    await ClockCycles(dut.clk, RX_BAUD_CYCLES)

    set_rx_pin(dut, 0)
    await ClockCycles(dut.clk, RX_BAUD_CYCLES)

    for i in range(8):
        set_rx_pin(dut, (byte_val >> i) & 0x1)
        await ClockCycles(dut.clk, RX_BAUD_CYCLES)

    set_rx_pin(dut, 1)
    await ClockCycles(dut.clk, RX_BAUD_CYCLES)


# ---------------------------------------------------------------------------
# RX observation helpers
# ---------------------------------------------------------------------------

async def wait_for_rx_valid(dut, timeout_cycles=200000):
    for _ in range(timeout_cycles):
        if get_rx_valid(dut) == 1:
            return
        await RisingEdge(dut.clk)
    assert False, "Timeout waiting for rx_valid"


async def wait_for_rx_valid_rise(dut, timeout_cycles=200000):
    prev = get_rx_valid(dut)
    for _ in range(timeout_cycles):
        cur = get_rx_valid(dut)
        if prev == 0 and cur == 1:
            return
        prev = cur
        await RisingEdge(dut.clk)
    assert False, "Timeout waiting for rx_valid rising edge"


async def send_frame_and_wait_rx_valid(dut, byte_val):
    t = cocotb.start_soon(wait_for_rx_valid(dut))
    await send_uart_frame_on_ui0(dut, byte_val)
    await t


async def send_frame_and_wait_rx_valid_rise(dut, byte_val):
    t = cocotb.start_soon(wait_for_rx_valid_rise(dut))
    await send_uart_frame_on_ui0(dut, byte_val)
    await t


# ---------------------------------------------------------------------------
# TX observation helpers
# ---------------------------------------------------------------------------

async def wait_for_tx_start(dut, timeout_cycles=200000):
    prev = get_tx_pin(dut)
    for _ in range(timeout_cycles):
        await RisingEdge(dut.clk)
        cur = get_tx_pin(dut)
        if prev == 1 and cur == 0:
            return
        prev = cur
    assert False, "Timeout waiting for TX start bit on uo_out[0]"


async def wait_for_tx_idle_high(dut, cycles):
    for _ in range(cycles):
        assert get_tx_pin(dut) == 1, "TX must remain high during idle"
        await RisingEdge(dut.clk)


async def sample_tx_frame_bits(dut):
    """Wait for a TX frame, skip start bit, return (data_bits[8], stop_bit).
    Samples at mid-bit boundaries using the nominal baud period."""
    await wait_for_tx_start(dut)
    await ClockCycles(dut.clk, TX_BAUD_CYCLES + (TX_BAUD_CYCLES // 2))
    bits = []
    for _ in range(8):
        bits.append(get_tx_pin(dut))
        await ClockCycles(dut.clk, TX_BAUD_CYCLES)
    stop_bit = get_tx_pin(dut)
    return bits, stop_bit


async def sample_tx_frame_structure(dut):
    """Wait for a TX frame and return (start_bit, data_bits[8], stop_bit).
    All samples taken at mid-bit for maximum setup/hold margin."""
    await wait_for_tx_start(dut)
    await ClockCycles(dut.clk, TX_BAUD_CYCLES // 2)
    start_bit = get_tx_pin(dut)
    await ClockCycles(dut.clk, TX_BAUD_CYCLES)
    bits = []
    for _ in range(8):
        bits.append(get_tx_pin(dut))
        await ClockCycles(dut.clk, TX_BAUD_CYCLES)
    stop_bit = get_tx_pin(dut)
    return start_bit, bits, stop_bit


# ===========================================================================
# RX PATH TESTS
# Tests exercise ui_in[0] as the serial RX line, independently of TX.
# ===========================================================================

@cocotb.test()
async def test_rx_idle_line_does_not_assert_valid(dut):
    """RX line held continuously high (idle) must never assert rx_valid."""
    await setup_clock(dut)
    await reset_dut(dut)
    set_rx_pin(dut, 1)
    for _ in range(RX_BAUD_CYCLES * 20):
        assert get_rx_valid(dut) == 0, \
            "rx_valid must stay low when RX line is continuously idle"
        await RisingEdge(dut.clk)


@cocotb.test()
async def test_rx_start_bit_required_for_frame(dut):
    """rx_valid must not assert when no low start bit has been sent."""
    await setup_clock(dut)
    await reset_dut(dut)
    set_rx_pin(dut, 1)
    await ClockCycles(dut.clk, RX_BAUD_CYCLES * 4)
    assert get_rx_valid(dut) == 0, \
        "rx_valid must not assert without a low start bit"


@cocotb.test()
async def test_rx_valid_asserts_after_complete_frame(dut):
    """A complete UART frame on RX must cause rx_valid to assert."""
    await setup_clock(dut)
    await reset_dut(dut)
    t = cocotb.start_soon(wait_for_rx_valid(dut))
    await send_uart_frame_on_ui0(dut, 0x55)
    await t


@cocotb.test()
async def test_rx_valid_deasserts_after_frame(dut):
    """rx_valid must pulse high and then deassert; it must not remain stuck."""
    await setup_clock(dut)
    await reset_dut(dut)
    t = cocotb.start_soon(wait_for_rx_valid_rise(dut))
    await send_uart_frame_on_ui0(dut, 0x5A)
    await t
    await ClockCycles(dut.clk, RX_BAUD_CYCLES * 3)
    assert get_rx_valid(dut) == 0, \
        "rx_valid must deassert after frame completion"


@cocotb.test()
async def test_rx_valid_not_asserted_before_stop_bit(dut):
    """rx_valid must not assert before the stop bit has been received."""
    await setup_clock(dut)
    await reset_dut(dut)
    set_rx_pin(dut, 1)
    await ClockCycles(dut.clk, RX_BAUD_CYCLES)
    set_rx_pin(dut, 0)  # start bit
    await ClockCycles(dut.clk, RX_BAUD_CYCLES)
    for i in range(8):
        set_rx_pin(dut, (0x55 >> i) & 0x1)
        await ClockCycles(dut.clk, RX_BAUD_CYCLES)
    assert get_rx_valid(dut) == 0, \
        "rx_valid must not assert before the stop bit is driven"
    t = cocotb.start_soon(wait_for_rx_valid(dut))
    set_rx_pin(dut, 1)  # stop bit
    await ClockCycles(dut.clk, RX_BAUD_CYCLES)
    await t


@cocotb.test()
async def test_rx_data_pattern_0x55(dut):
    """Receiver must correctly decode 0x55 (alternating bits, LSB=1)."""
    await setup_clock(dut)
    await reset_dut(dut)
    await send_frame_and_wait_rx_valid(dut, 0x55)
    assert get_rx_data(dut) == 0x55, f"Expected rx_data=0x55, got {get_rx_data(dut):#04x}"


@cocotb.test()
async def test_rx_data_pattern_0xAA(dut):
    """Receiver must correctly decode 0xAA (alternating bits, LSB=0)."""
    await setup_clock(dut)
    await reset_dut(dut)
    await send_frame_and_wait_rx_valid(dut, 0xAA)
    assert get_rx_data(dut) == 0xAA, \
        f"Expected rx_data=0xAA, got {get_rx_data(dut):#04x}"


@cocotb.test()
async def test_rx_data_pattern_0x00(dut):
    """Receiver must correctly decode 0x00 (all-zero payload)."""
    await setup_clock(dut)
    await reset_dut(dut)
    await send_frame_and_wait_rx_valid(dut, 0x00)
    assert get_rx_data(dut) == 0x00, \
        f"Expected rx_data=0x00, got {get_rx_data(dut):#04x}"


@cocotb.test()
async def test_rx_data_pattern_0xFF(dut):
    """Receiver must correctly decode 0xFF (all-one payload)."""
    await setup_clock(dut)
    await reset_dut(dut)
    await send_frame_and_wait_rx_valid(dut, 0xFF)
    assert get_rx_data(dut) == 0xFF, \
        f"Expected rx_data=0xFF, got {get_rx_data(dut):#04x}"


@cocotb.test()
async def test_rx_data_pattern_0x3C(dut):
    """Receiver must correctly decode 0x3C (mixed bit pattern)."""
    await setup_clock(dut)
    await reset_dut(dut)
    await send_frame_and_wait_rx_valid(dut, 0x3C)
    assert get_rx_data(dut) == 0x3C, \
        f"Expected rx_data=0x3C, got {get_rx_data(dut):#04x}"


@cocotb.test()
async def test_rx_data_pattern_0xA5(dut):
    """Receiver must correctly decode 0xA5 (mixed bit pattern)."""
    await setup_clock(dut)
    await reset_dut(dut)
    await send_frame_and_wait_rx_valid(dut, 0xA5)
    assert get_rx_data(dut) == 0xA5, \
        f"Expected rx_data=0xA5, got {get_rx_data(dut):#04x}"


@cocotb.test()
async def test_rx_back_to_back_frames(dut):
    """Receiver must correctly decode consecutive frames without a reset between them."""
    await setup_clock(dut)
    await reset_dut(dut)
    patterns = [0x12, 0x34, 0x56, 0x78]
    for byte_val in patterns:
        await send_frame_and_wait_rx_valid(dut, byte_val)
        assert get_rx_data(dut) == byte_val, (
            f"Back-to-back RX mismatch for {byte_val:#04x}: "
            f"got {get_rx_data(dut):#04x}"
        )
        await ClockCycles(dut.clk, RX_BAUD_CYCLES * 2)


@cocotb.test()
async def test_rx_data_stable_while_valid_asserted(dut):
    """rx_data must hold its value for the duration that rx_valid is asserted."""
    await setup_clock(dut)
    await reset_dut(dut)
    await send_frame_and_wait_rx_valid_rise(dut, 0x71)
    captured = get_rx_data(dut)
    assert captured == 0x71, f"Initial rx_data mismatch: expected 0x71, got {captured:#04x}"
    for _ in range(RX_BAUD_CYCLES):
        if get_rx_valid(dut) == 0:
            break
        assert get_rx_data(dut) == captured, \
            "rx_data changed while rx_valid was still asserted"
        await RisingEdge(dut.clk)


# ===========================================================================
# TX PATH TESTS
# Tests exercise uo_out[0] as the serial TX line, independently of RX data.
# wr_enb is uio_in[0]; tx_data is ui_in (use bytes with bit0=1 so RX stays idle).
# ===========================================================================

@cocotb.test()
async def test_tx_idle_high_after_reset(dut):
    """TX line must be high immediately after reset is deasserted."""
    await setup_clock(dut)
    await reset_dut(dut)
    assert get_tx_pin(dut) == 1, "TX must be high after reset"


@cocotb.test()
async def test_tx_stays_high_while_idle(dut):
    """TX line must remain continuously high during an idle period."""
    await setup_clock(dut)
    await reset_dut(dut)
    await wait_for_tx_idle_high(dut, TX_BAUD_CYCLES * 5)


@cocotb.test()
async def test_tx_no_spurious_frame_without_wr_enb(dut):
    """TX must not transmit a frame when wr_enb has never been asserted."""
    await setup_clock(dut)
    await reset_dut(dut)
    for _ in range(TX_BAUD_CYCLES * 10):
        assert get_tx_pin(dut) == 1, \
            "TX must not transmit without wr_enb being asserted"
        await RisingEdge(dut.clk)


@cocotb.test()
async def test_tx_starts_after_wr_enb(dut):
    """TX must begin a frame (fall low for start bit) after wr_enb asserts."""
    await setup_clock(dut)
    await reset_dut(dut)
    await issue_tx_write(dut, 0x55)
    await wait_for_tx_start(dut)


@cocotb.test()
async def test_tx_start_bit_is_low(dut):
    """The first element of any TX frame must be a logic-low start bit."""
    await setup_clock(dut)
    await reset_dut(dut)
    await issue_tx_write(dut, 0x55)
    start_bit, _, _ = await sample_tx_frame_structure(dut)
    assert start_bit == 0, f"Start bit must be 0, got {start_bit}"


@cocotb.test()
async def test_tx_stop_bit_is_high(dut):
    """The last element of any TX frame must be a logic-high stop bit."""
    await setup_clock(dut)
    await reset_dut(dut)
    await issue_tx_write(dut, 0x55)
    _, _, stop_bit = await sample_tx_frame_structure(dut)
    assert stop_bit == 1, f"Stop bit must be 1, got {stop_bit}"


@cocotb.test()
async def test_tx_transmits_exactly_eight_data_bits(dut):
    """TX frame must contain exactly 8 data bits between start and stop bits."""
    await setup_clock(dut)
    await reset_dut(dut)
    await issue_tx_write(dut, 0x55)
    _, bits, _ = await sample_tx_frame_structure(dut)
    assert len(bits) == 8, f"Expected 8 data bits in TX frame, counted {len(bits)}"


@cocotb.test()
async def test_tx_bit_stable_across_baud_period(dut):
    """Each TX bit must remain stable for the full baud period with no glitches."""
    await setup_clock(dut)
    await reset_dut(dut)
    await issue_tx_write(dut, 0x55)
    await wait_for_tx_start(dut)
    # Advance to quarter-mark of the start bit
    await ClockCycles(dut.clk, TX_BAUD_CYCLES // 4)
    # For each bit (start + 8 data), sample at 1/4 and 3/4 through the period
    for _ in range(9):
        early = get_tx_pin(dut)
        await ClockCycles(dut.clk, TX_BAUD_CYCLES // 2)
        late = get_tx_pin(dut)
        assert early == late, \
            f"TX bit changed within its baud period: {early} → {late}"
        await ClockCycles(dut.clk, TX_BAUD_CYCLES // 2)


@cocotb.test()
async def test_tx_returns_to_idle_after_frame(dut):
    """TX must return to logic-high idle and hold there after the stop bit."""
    await setup_clock(dut)
    await reset_dut(dut)
    await issue_tx_write(dut, 0xA5)
    await wait_for_tx_start(dut)
    # Wait for the complete frame: start + 8 data + stop + margin
    await ClockCycles(dut.clk, TX_BAUD_CYCLES * 12)
    assert get_tx_pin(dut) == 1, "TX must return to idle high after one frame"
    await wait_for_tx_idle_high(dut, TX_BAUD_CYCLES * 6)


@cocotb.test()
async def test_tx_reset_during_frame_forces_idle(dut):
    """Assert reset mid-transmission; TX must immediately return to idle high."""
    await setup_clock(dut)
    await reset_dut(dut)
    await issue_tx_write(dut, 0x55)
    await wait_for_tx_start(dut)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 2)
    assert get_tx_pin(dut) == 1, "TX must return high during active reset"
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)
    assert get_tx_pin(dut) == 1, "TX must remain idle high after reset deassertion"


@cocotb.test()
async def test_tx_data_lsb_first_0x55(dut):
    """TX must serialize 0x55 LSB-first (0x55 has LSB=1 for ui_in[0] idle)."""
    await setup_clock(dut)
    await reset_dut(dut)
    await issue_tx_write(dut, 0x55)
    bits, stop_bit = await sample_tx_frame_bits(dut)
    assert bits == bits_lsb_first(0x55), \
        f"Expected LSB-first 0x55, got {bits}"
    assert stop_bit == 1, "Stop bit must be high"


@cocotb.test()
async def test_tx_data_lsb_first_0xFF(dut):
    """TX must serialize 0xFF LSB-first (0xFF has LSB=1 for ui_in[0] idle)."""
    await setup_clock(dut)
    await reset_dut(dut)
    await issue_tx_write(dut, 0xFF)
    bits, stop_bit = await sample_tx_frame_bits(dut)
    assert bits == bits_lsb_first(0xFF), \
        f"Expected LSB-first 0xFF, got {bits}"
    assert stop_bit == 1, "Stop bit must be high"
