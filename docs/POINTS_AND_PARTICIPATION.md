# Points & Real Participation Evidence

One of the fundamental design principles of `quip-android-aglais-node` is the **rejection of simulated progress, mock data, and unearned point counters**.

---

## 1. Official Aglais Testnet Points Rules

According to official Quip Network documentation:
- **Participation Points**: 1 point awarded per distinct qblock participated in.
- **Daily Participation Cap**: Strictly capped at **72 participation points per UTC day**.
- **Win Points**: 20 points awarded per qblock won.
- **Infrastructure Multipliers**: Apply exclusively to base participation points.
- **On-Chain Truth**: Actual points balances are recorded on-chain by the Aglais network consensus. Running the miner process briefly does NOT guarantee that the network accepted your solution into a qblock.

---

## 2. Pluggable Evidence Architecture

The controller implements a pluggable `ParticipationProvider` interface:

```python
class ParticipationProvider(ABC):
    @abstractmethod
    def process_line(self, line: str, session_id: str) -> Optional[Evidence]:
        ...
```

### Supported Providers:
1. **MinerLogProvider (Default)**: Inspects streaming miner console output for cryptographic solver events (e.g. `participating in qblock #...`, `challenge accepted`, `won qblock #...`).
2. **TelemetryProvider**: Captures telemetry frames emitted by `quip-miner telemetry`.
3. **SubstrateEventProvider (Extensible)**: Subscribes to Substrate runtime events.

If the miner is running but no participation lines have yet been confirmed, the UI accurately states:
> *"Mining is running, but participation has not yet been independently verified."*

---

## 3. Persistent Evidence Journal (`data/participation.jsonl`)

Every verified event is appended atomically to `data/participation.jsonl` with full audit fields:

```json
{
  "timestamp": "2026-09-11T20:15:30Z",
  "session_id": "20260911_201000",
  "network": "aglais",
  "evidence_source": "miner_logs",
  "qblock_id": "48291",
  "participation_status": "verified",
  "win_status": false,
  "raw_evidence": "[20:15:30] participating in qblock #48291 solver mode"
}
```

---

## 4. Local Points Estimator

The local points estimator evaluates the journal records for the current UTC day and computes:
$$\text{Total Points} = \min(\text{Distinct Qblocks}, 72) \times \text{Multiplier} + (\text{Wins} \times 20)$$

On Android mobile installations, infrastructure bonuses (e.g. `public_p2p`, `public_api`, `tls`) are explicitly flagged as **"Not verified / unavailable on Android"** and excluded from the multiplier calculation to prevent inflated estimates.
