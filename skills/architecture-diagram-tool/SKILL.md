---
name: architecture-diagram-tool
description: Draw, redesign, beautify, review, and standardize cloud architecture diagrams for Huawei Cloud and other providers. Use official service icons when available, white/red or provider-brand styling, logically layered layouts, non-overlapping boxes, orthogonal non-crossing connectors, clear trust boundaries, and validated geometry.
---

# 架构图工具

## Overview

Use this skill for architecture diagrams that must be both technically credible and presentation-ready. Default to a static HTML/SVG visual when official icons, branded styling, precise spacing, or non-crossing routing matter; use Mermaid only for a simple first-pass structure. Treat the layout as a constrained geometry problem: place boundaries and boxes first, reserve routing corridors, route edges second, then validate the rendered result.

Keep the semantic model separate from the renderer. The same architecture may be rendered as:

- HTML/SVG for presentation-ready branded diagrams with exact geometry and embedded official icons.
- PlantUML when fast container-based layout and provider stencil libraries are the priority.
- Draw.io when the user needs an editable `.drawio` source, explicit waypoints, or a single-viewport deliverable.
- ELK JSON/SVG when layered DAG layout, compound groups, and a reproducible source/render pair are useful.
- Mermaid `architecture-beta` only for small topology drafts; keep service count small and use explicit connection directions.

When using a non-native renderer, preserve the user's provider icon requirement by reusing verified provider assets; do not substitute generic icons merely because a renderer has a built-in icon vocabulary.

## Workflow

### 1. Clarify the architecture before drawing

- Identify the business flow, data flow, control/telemetry flow, and recovery flow.
- Identify trust and deployment boundaries: Internet, office/IDC, VPC/VNet, subnets, AZs, regions, production, backup, and recovery.
- Capture assumptions that materially affect the drawing: traffic direction, managed versus self-managed services, RTO/RPO, cross-region replication, compliance, and optional components.
- Do not add services merely to fill space. Every node needs a role and every connector needs a meaning.

### 2. Choose a layout that prevents crossings

- Use a left-to-right primary business path: entry → edge → network → compute → data.
- Put security, observability, IAM, or governance in a separate top or right control plane; connect it with dashed orthogonal lines routed through reserved lanes.
- Put backup, replication, and recovery in a separate bottom data-protection plane; do not route recovery lines through production nodes.
- Use rectangular sections with clear headers. Avoid narrow sidebars that force long labels to overflow.
- Reserve at least 24 px between cards, 32 px between sections, and 40 px around the outer canvas. Keep labels inside cards and leave whitespace around every connector.
- Use a grid. Align cards by their centerline and route connectors at fixed horizontal/vertical lanes rather than freehand diagonals.
- If a line must change direction, use 90-degree elbows with one bend lane. Never let a connector pass through a node, label, section title, or another connector.
- Treat every card, boundary, title, legend, and label as a collision object. A deliverable fails validation if card interiors overlap, a connector enters a card except at its intended endpoint, or connectors cross. Border-touching is allowed only when it is an intentional shared boundary.
- Use distinct input/output ports and dedicated horizontal/vertical corridors. If multiple flows share a route, merge them at a labeled hub and fan out later; do not draw coincident or crossing lines on top of one another.

For dense diagrams, establish a source of truth before styling:

1. Write the node/edge inventory and mark each edge as business, control, telemetry, backup, replication, or recovery.
2. Pick the renderer based on the deliverable, not habit.
3. Place compound boundaries first, then nodes, then named routing corridors, then labels.
4. Render the source and inspect the actual output at the target presentation width.

Prefer one overview diagram with roughly 6–20 meaningful nodes. Split a detailed control or recovery view when extra nodes would force smaller text or ambiguous edges.

Detailed geometry and routing patterns are in [references/layout-rules.md](references/layout-rules.md). When a geometry JSON is available, run `python scripts/validate_geometry.py <layout.json>` and fix every failure before handoff.

### 3. Use icons and brand styling correctly

- Prefer the provider's official architecture icon library or official product-page assets. For Huawei Cloud, use the maintained `huaweicloud-latam/drawio-libraries` `color` set; do not use the legacy `line` set when the user asks for current official icons.
- Keep service icon colors official, but make the canvas and containers coherent: white background, restrained light fills, one primary brand accent, and neutral gray connector/annotation colors.
- For Huawei Cloud, use Huawei red as the primary accent. For other providers, use their current brand accent only after confirming the provider and icon source.
- This Skill bundles the Huawei Cloud icon libraries under `assets-huawei-cloud-color/` (default, current color XML libraries) and `assets-huawei-cloud-line/` (legacy line libraries for compatibility only). Read [references/huawei-icon-source.md](references/huawei-icon-source.md) before selecting Huawei icons; prefer the color bundle and use exact service names from the library.
- Embed local SVG/data-URI icon assets when the visual must render reliably in the conversation. Do not rely on unapproved remote image origins.
- Shorten labels to `product name + role`; move long explanations into a section subtitle or footnote. Never shrink text below readable size just to fit a card.

### 4. Make the logic explicit

- Solid red/provider-colored arrows: business or data path.
- Dashed neutral or accent arrows: logs, telemetry, policy, orchestration, or management control.
- Separate backup/recovery arrows from production traffic. Use a dedicated recovery node or recovery zone.
- Do not imply unsupported service behavior. For example, do not draw a host agent inside a managed database unless the provider explicitly supports it; represent database-native backup/audit separately.
- Make optional services visually explicit with “可选” and keep them off the critical path unless they are required.
- For security diagrams, show the response loop: detection → analysis → isolation/blocking → backup/recovery. For ordinary application diagrams, show the normal request/data lifecycle without inventing security controls.

### 5. Validate before handoff

- Semantic check: every arrow has a clear source, destination, direction, and purpose; service placement matches the provider's actual capability.
- Geometry check: no connector intersects another connector, card, icon, text, header, or boundary unless an explicit junction is intended. If two flows share a route, merge them at a labeled hub rather than crossing them.
- Readability check: no text is truncated or overlapping; nodes remain legible at the target presentation width; long labels are wrapped or shortened.
- Visual check: the primary flow can be followed in one pass; control and recovery planes are visually distinct; whitespace is intentional; colors do not overpower the architecture.
- Source check: official icon source and important product assumptions are noted in a small footer or accompanying prose.
- Render the HTML/SVG after edits and inspect the actual result. Re-route before adding more nodes when the diagram becomes dense.
- Editable-source check: when the chosen renderer supports it, retain the PlantUML, Draw.io XML, or ELK JSON source alongside the rendered SVG/HTML.

## Recommended final structure

Use this composition unless the user requests another style:

1. Header: title, scope, and a short legend.
2. Primary path: users/partners → ingress/edge → network → compute → data.
3. Control plane: security, IAM, observability, governance, or operations.
4. Data-protection plane: backup, replication, DR, and recovery validation.
5. Footer: icon source, assumptions, and optional-service notes.

If the user requests an editable deliverable, preserve the HTML/SVG source and, where practical, provide an SVG or draw.io-compatible version rather than a flattened bitmap.

## Provider mapping

Keep the architecture model provider-neutral until the user chooses a provider. Then map each role to that provider's managed service and official icon. If the user asks for several providers, keep the same semantic layout and change only the service mapping, icon set, and brand accent; do not change the flow merely to make products appear comparable.

## Portability

- Keep all references and icon assets relative to this Skill directory; do not require network access at render time.
- The bundled geometry validator uses only Python's standard library and can run in a restricted agent environment.
- The `agents/openai.yaml` file is host metadata for Codex; other hosts may ignore it and still use `SKILL.md`, `scripts/`, `references/`, and `assets-*`.
- The runtime slug is intentionally lowercase and hyphenated as `architecture-diagram-tool`; hosts may display it as the localized name “架构图工具”.
