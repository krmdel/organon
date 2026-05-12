import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { listSkills, type Skill } from "../skills";
import { organonRoot } from "../paths";

export type ToolCatalogEntry = {
  id: string;
  name: string;
  description: string;
  category: string;
  source: "skill" | "mcp";
  mcp_server?: string;
  /** Trigger phrases / keywords for the search box. */
  triggers: string[];
};

function skillToEntry(s: Skill): ToolCatalogEntry {
  return {
    id: s.name,
    name: s.name,
    description: s.description,
    category: s.category,
    source: "skill",
    triggers: [],
  };
}

function readMcpServers(): { server: string; command: string }[] {
  const target = path.join(organonRoot(), ".mcp.json");
  if (!existsSync(target)) return [];
  try {
    const raw = JSON.parse(readFileSync(target, "utf8")) as {
      mcpServers?: Record<string, { command?: string; args?: string[]; url?: string }>;
    };
    if (!raw.mcpServers) return [];
    return Object.entries(raw.mcpServers).map(([server, def]) => ({
      server,
      command: def.command ?? (def.url ? `http: ${def.url}` : "(no command)"),
    }));
  } catch {
    return [];
  }
}

export function buildCatalog(): ToolCatalogEntry[] {
  const out: ToolCatalogEntry[] = [];
  for (const s of listSkills()) out.push(skillToEntry(s));
  for (const mcp of readMcpServers()) {
    out.push({
      id: `mcp:${mcp.server}`,
      name: mcp.server,
      description: `MCP server (transport: ${mcp.command.startsWith("http:") ? "http" : "stdio"})`,
      category: "mcp",
      source: "mcp",
      mcp_server: mcp.server,
      triggers: [],
    });
  }
  return out;
}
