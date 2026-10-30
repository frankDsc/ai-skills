# Layout and routing rules

## Canonical lanes

Use these lanes for a dense but readable architecture diagram:

```text
top:        title + legend
upper:      external actors and ingress / edge services
middle:     primary business path inside the cloud boundary
right/top:  control plane (logs, IAM, security, observability, operations)
bottom:     backup, replication, disaster recovery, and restore validation
footer:     icon source and assumptions
```

The primary path should be monotonic from left to right. Keep control and recovery lines out of the primary path whenever possible.

## Renderer selection

Choose the renderer from the deliverable:

| Need | Preferred renderer | Layout discipline |
| --- | --- | --- |
| Presentation-ready branded visual | HTML/SVG | Fixed grid, embedded official icons, explicit corridors |
| Fast provider-stencil draft | PlantUML | Nested containers, left-to-right direction, short labels |
| Editable diagram and explicit waypoints | Draw.io | Complete XML, read-before-edit, single viewport |
| Layered dependency graph | ELK JSON/SVG | Compound nodes, layered algorithm, keep source and render |
| Small semantic topology | Mermaid architecture-beta | 6–8 services, explicit port directions |

Regardless of renderer, keep the node/edge inventory as the source of truth and make the rendered result pass the same semantic and geometry checks.

## Source and density policy

- Use one overview view for about 6–20 meaningful nodes; split detailed security, data, or recovery views when labels or edges become dense.
- Boundaries are drawn before nodes; routing corridors are reserved before edges; labels are added after routes are stable.
- Keep provider-specific icons and capability assumptions independent from renderer syntax so a provider mapping can change without changing the flow model.

## Connector policy

- Use orthogonal connectors: horizontal and vertical segments only.
- Reserve named routing corridors before drawing connectors. A connector may occupy one corridor at a time.
- Never cross a node or a section header. Do not place a label on top of a line.
- Prefer separate entry/exit ports on the same card instead of joining two edges at a corner.
- When multiple sources feed one service, route them to a small hub or the service's left-side input rail. When one source fans out, use a right-side output rail.
- If two connectors would cross, change the lane or reorder the nodes. Do not hide the crossing with color or opacity.
- Use solid lines for business/data flow and dashed lines for telemetry/control. Use one arrowhead style throughout.
- Keep arrowheads at least 8 px away from a card border; terminate on the card edge, not on an icon or label.

## Hard geometry gate

Before delivery, the source layout must satisfy all of these rules:

- Card interiors have no positive-area intersection. A shared boundary is allowed only when it represents an intentional nested boundary.
- A connector may touch its source/target port, but may not enter any unrelated card, section header, legend, icon, or label.
- Orthogonal connector segments do not cross. Collinear overlap is also a failure unless it is represented as one shared route with an explicit hub.
- A connector must not pass through a boundary that it does not belong to; use a labeled gateway/port when crossing trust boundaries.
- Geometry validation is executable with the bundled standard-library script: `python scripts/validate_geometry.py <layout.json>`. A non-zero exit code blocks handoff.

The JSON input uses `nodes: [{id, x, y, w, h}]` and `edges: [{id, points: [[x, y], ...]}]`. Coordinates are in the final renderer's viewport units.

## Spacing targets

- Outer canvas margin: 40–56 px.
- Section-to-section gap: at least 32 px.
- Card-to-card gap: at least 24 px.
- Card internal padding: at least 16 px.
- Text line height: at least 1.4× font size.
- Preferred card minimum: 170×86 px for icon + two lines; use a wider card for long provider names.
- Keep a dedicated 24–36 px routing lane between card rows.

## Density escape hatches

When the diagram is too dense, use these in order:

1. Remove optional services from the critical path and mark them in a small extension area.
2. Shorten labels to service name + role; move detail to a note or footer.
3. Split control and recovery into their own lanes.
4. Increase canvas width before reducing text size.
5. Split one diagram into an overview and one detailed sub-diagram if the user needs both executive readability and implementation detail.

## Logic review checklist

- Is the traffic path in the correct order for the chosen provider?
- Are managed services distinguished from resources that require agents or deployment?
- Does every data source have a destination for storage, backup, or recovery?
- Are cross-AZ and cross-region flows explicitly labeled rather than implied?
- Are optional components off the critical path?
- Does the recovery path end in a clean recovery zone instead of looping ambiguously into production?
- Are all observability/security/control arrows dashed and visually separated from business traffic?
