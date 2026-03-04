import { SatelliteError } from "../utils/errors.js";

const GITHUB_API_BASE = "https://api.github.com";

export class GitHubClient {
  private headers: Record<string, string>;

  constructor(token: string) {
    this.headers = {
      Authorization: `token ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    };
  }

  private async request(method: string, path: string, body?: unknown): Promise<Record<string, unknown>> {
    const response = await fetch(`${GITHUB_API_BASE}${path}`, {
      method,
      headers: {
        ...this.headers,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status >= 400) {
      let message: string;
      try {
        const data = (await response.json()) as Record<string, unknown>;
        message = typeof data.message === "string" ? data.message : `HTTP ${response.status}`;
      } catch {
        message = `HTTP ${response.status}`;
      }
      throw new SatelliteError(
        `GitHub API error ${response.status}: ${message}`,
        "GITHUB_ERROR",
      );
    }

    if (response.status === 204) return {};
    return (await response.json()) as Record<string, unknown>;
  }

  async checkAuth(): Promise<string> {
    const data = await this.request("GET", "/user");
    return data.login as string;
  }

  async hasPushAccess(repo: string): Promise<boolean> {
    try {
      const data = await this.request("GET", `/repos/${repo}`);
      const permissions = data.permissions as Record<string, boolean> | undefined;
      return permissions?.push ?? false;
    } catch (err) {
      if (err instanceof SatelliteError && err.message.includes("403")) return false;
      if (err instanceof SatelliteError && err.message.includes("404")) return false;
      throw err;
    }
  }

  async ensureFork(repo: string): Promise<string> {
    const data = await this.request("POST", `/repos/${repo}/forks`);
    return data.full_name as string;
  }

  async getDefaultBranchSha(repo: string): Promise<string> {
    const data = await this.request("GET", `/repos/${repo}/git/ref/heads/main`);
    const obj = data.object as Record<string, string>;
    return obj.sha;
  }

  async createBranch(repo: string, branch: string, sha: string): Promise<void> {
    await this.request("POST", `/repos/${repo}/git/refs`, {
      ref: `refs/heads/${branch}`,
      sha,
    });
  }

  async uploadFiles(
    repo: string,
    branch: string,
    files: Array<{ path: string; content: Buffer }>,
  ): Promise<string> {
    // 1. Get branch HEAD SHA
    const refData = await this.request("GET", `/repos/${repo}/git/ref/heads/${branch}`);
    const baseSha = (refData.object as Record<string, string>).sha;

    // 2. Get tree SHA from commit
    const commitData = await this.request("GET", `/repos/${repo}/git/commits/${baseSha}`);
    const baseTreeSha = (commitData.tree as Record<string, string>).sha;

    // 3. Create blobs for each file
    const treeItems: Array<Record<string, string>> = [];
    for (const file of files) {
      const blobData = await this.request("POST", `/repos/${repo}/git/blobs`, {
        content: file.content.toString("base64"),
        encoding: "base64",
      });
      treeItems.push({
        path: file.path,
        mode: "100644",
        type: "blob",
        sha: blobData.sha as string,
      });
    }

    // 4. Create tree
    const treeData = await this.request("POST", `/repos/${repo}/git/trees`, {
      base_tree: baseTreeSha,
      tree: treeItems,
    });

    // 5. Create commit
    const commitResult = await this.request("POST", `/repos/${repo}/git/commits`, {
      message: `Add trajectory files (${files.length} files)`,
      tree: (treeData as Record<string, unknown>).sha as string,
      parents: [baseSha],
    });

    const newSha = commitResult.sha as string;

    // 6. Update branch ref
    await this.request("PATCH", `/repos/${repo}/git/refs/heads/${branch}`, {
      sha: newSha,
    });

    return newSha;
  }

  async createPR(
    baseRepo: string,
    head: string,
    title: string,
    body: string,
  ): Promise<string> {
    const data = await this.request("POST", `/repos/${baseRepo}/pulls`, {
      title,
      body,
      head,
      base: "main",
    });
    return data.html_url as string;
  }
}
