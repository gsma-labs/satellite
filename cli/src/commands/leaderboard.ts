import { fetchLeaderboard } from "../services/leaderboard-client.js";
import { emitJSON } from "../utils/output.js";
import { exitWithError } from "../utils/errors.js";

export async function leaderboardCommand(): Promise<void> {
  try {
    const entries = await fetchLeaderboard();
    emitJSON(entries);
  } catch (err) {
    exitWithError(
      err instanceof Error ? err.message : String(err),
      "NETWORK_ERROR",
    );
  }
}
