# Sculpt Helper

A Blender 5.x extension that makes Sculpt Mode faster: hold keys for masking and
isolating, quick panels, and helper tools that stock Blender lacks.

Status: **all steps done, including the custom-drawn UI** (hold keys, pie menus, sidebar panels, sculpt
helpers, advanced tools). See the plan below.

## Install

1. Build the zip: `python build.py` (creates `dist/sculpt_helper-<version>.zip`).
   Blender's own builder works too: `blender --command extension build --source-dir sculpt_helper`.
2. In Blender: *Edit > Preferences > Get Extensions > ∨ > Install from Disk…*
   and pick the zip.

## Shortcuts (Sculpt Mode)

All of them can be rebound in *Preferences > Add-ons > Sculpt Helper*. **F1**
shows the current list in the viewport.

| Key | Action |
| --- | --- |
| **C** (hold) | Mask brush while held, previous brush comes back on release. Drag on mesh paints mask, **Ctrl**+drag removes it. Click on mesh blurs the mask, **Ctrl**+click sharpens it. Click on background inverts the mask, drag on background clears it. |
| **Shift+C** (hold) | Isolate. Drag a box / lasso / line to show only that area (**Ctrl** on release hides it instead). **Tab** or the mouse wheel changes the shape. Click a face set to show only it, click again to show all. Click the background to show everything. |
| **Q** | Brush wheel: a drawn ring of brush thumbnails around the cursor, hovered name in the centre. Click a brush, or point at one and let go of Q. Right-click closes. Any number of brushes (a second ring appears past twelve). Turn *Custom Brush Wheel* off in Preferences to get the native pie instead (seven favourites plus the full brush browser). Edit the brush list in Preferences. |
| **A** | Mask pie: invert, clear, fill, blur, sharpen, grow, shrink, contrast, from cavity. |
| **Shift+W** | Hide / Show pie: show all, invert, hide / show masked, grow / shrink visible, hide tools. |
| **Alt+W** | Face Sets pie: from mask / visible, auto create, new colours, Draw Face Sets brush. |
| **Z** | View / Mode popup: mirror, display overlays, Dyntopo and Multires in one place. |
| **S** | Choose which sidebar panels are shown. |
| **Y** | Pivot bend / twist (see below). |
| **F1** | Shortcut list. |

These replace some Blender defaults in Sculpt Mode while the add-on is enabled
(C Clay Strips, Shift+C Crease Polish, S Smooth, Q Quick Favourites, Z shading
pie, A / Alt+W Blender's own mask and face set pies). The preferences show
every default binding that is overridden, and any key can be changed there.

## Floating panels

In the **S** popup, *Floating Panels* turns on draggable cards drawn in the
viewport, with a tab bar on the right edge to open and close each one (the
top button turns floating mode off). Drag a card by its header; the header
buttons collapse it (▾), explain it (?), open the full sidebar panel as a
popup (≡) and close it (×). Cards hold the most used controls of each panel:
radius / strength sliders and auto-masking, mask and visibility actions,
mirror and overlays, deform filters with Pivot Bend and Gizmo, layers with
strength sliders, and so on. Positions are remembered. Cards show only in
the viewport they were started in and only in Sculpt Mode; clicks outside
them go to Blender as usual.

Blender doesn't autosave while floating mode is on (it keeps a modal
operator running), so turn it off or save by hand during long sessions.

## Sidebar panels (N > Sculpt Helper)

Each panel has a **?** button explaining it, and **S** hides the ones you
don't need.

| Panel | Contents |
| --- | --- |
| Brush | Brush picker, radius and strength with pressure toggles, Texture / Stroke / Falloff popovers, auto-masking toggles. |
| Mask / Hide | Mask invert / clear / blur / sharpen / grow / shrink; show all, invert, hide / show masked, grow / shrink visible; hold-isolate shape. |
| View / Mode | Mirror X / Y / Z and Symmetrize; mask, face set and wireframe overlays; Dyntopo toggle, detail settings and flood fill. |
| Deform | Mesh filters with strength and iterations: smooth, surface smooth, inflate / deflate, expand / shrink, sphere, random, sharpen, enhance, relax. |
| Face Sets | Create from mask / visible, auto create, new colours, overlay opacity, Edit Face Set tool. |
| Vertex Color | Colour wheel, primary / secondary colour, palette swatches, Paint brush, fill. |
| Material | MatCap / Studio / Flat lighting, MatCap picker and flip, object colour, cavity. |
| Multires | Subdivide (smooth / simple / linear, adds the modifier if needed), level − / + with linked levels, delete higher, apply base. |
| Extract | Extract or slice the masked area, extract a face set. |
| Layers | Sculpt layers with strength sliders and mute. |
| Remesh | Voxel size and options, Voxel Remesh, QuadriFlow, Shape Transfer. |
| Boolean | Cutters (sphere / cube / cylinder) kept as editable Boolean layers until confirmed. |
| History | Snapshot timeline with branches, Blend, Paint Back and the Morph Target brush. |

## Sculpt helpers

| Tool | Where | What it does |
| --- | --- | --- |
| Thickness Protect | Brush > Auto-Masking | Front faces only plus occlusion masking, so strokes don't reach through thin parts. |
| Depth Limit | Brush > Depth Limit | Record Shape, then nothing can rise more than Max Height or sink more than Max Depth from it. Auto applies it after every stroke; Apply Now does it once. |
| Gravity | Brush > Gravity | Gravity strength, aimed at the screen bottom, into the screen, world down, or a dragged direction. |
| Save / Load masks | Mask / Hide > Save / Load | Named masks stored on the mesh; load, add, subtract or intersect them with the current mask. |
| Morph | Deform > Morph | Record Shape, sculpt, mask where you want the old shape back, press Morph Masked (or Morph Unmasked). |
| Copy Stamp | Deform > Copy Stamp | Click to sample the surface detail under the brush, click elsewhere to stamp it (Shift+click resamples). Detail Size decides how large a feature counts as detail; Replace Detail swaps the target's own detail for the copy. |
| Material by mask | Material | Assign the active material slot to the masked faces, or mask the faces using it. |
| Sculpt Together | View / Mode > Sculpt Together | Select several meshes and Combine: copies are joined into one object (one face set each) and the originals hidden. Split Back writes each part into its original object, keeping name, transform, modifiers and materials. |

## Advanced tools

| Tool | Where | What it does |
| --- | --- | --- |
| Pivot Bend | **Y**, or Deform > Pivot Bend | Click a joint to drop a pivot in the middle of the limb, drag the pivot to bend the part beyond it; **T** switches to twist. Hold **W** / **R** and move the mouse for blend width (root side) and bend length (curls necks and tails). **M** keeps masked areas still, **K** smooths the joint, **I** shows what will move, **X** or Alt+click deletes a pivot. Works on chains of joints, and mirrors when X symmetry is on. |
| Gizmo | Deform > Gizmo, or the A pie | Mask what should stay, then move, rotate and scale the unmasked part with a gizmo. Pivot at its centre, on the mask border (joints) or the origin. |
| Sculpt Layers | Layers panel | Add a layer and sculpt: changes go into the recording (●) layer. Fade layers with their slider, mute them, delete them (removes their change) or Apply All. |
| Shape Transfer | Remesh > Shape Transfer | Remesh (Keep Detail) voxel-remeshes and pulls the result back onto the old surface. Transfer Shape pulls the unmasked surface onto another object. |
| History Timeline | History panel, Timeline button | Snapshots every N strokes (default 5) plus ones you take by hand. Click one to select it; Jump (or double-click on the timeline) restores it, even after a remesh. Sculpting from an older snapshot starts a branch, so nothing is lost. Blend slides between now and the selected snapshot; Paint Back restores it where you mask. The Timeline button draws the tree with thumbnails along the bottom of the viewport. Optional Keep in File stores snapshots in the .blend. |
| Morph Target Brush | History panel, or the Brush button on the timeline | Paint the surface back toward the selected snapshot or the Recorded Shape. Uses the current brush radius; Esc or right-click to finish. |
| Boolean Layers | Boolean panel | Add cutters at the 3D cursor; change operation, hide, Edit (move / scale in Object Mode, then Back to Sculpting) or remove each one. Confirm applies them all, Cancel discards them. |

Depth Limit, Morph, Copy Stamp, saved masks, material by mask, Pivot Bend and
Sculpt Layers, Blend, Paint Back and the Morph Target brush edit vertex
data directly, so they briefly leave Sculpt Mode and come back (each use is one
undo step). Like the reference add-on, they don't work with Dyntopo on, a
Multires modifier, or shape keys; the panel says so when that's the case.
Sculpt Together doesn't keep vertex groups, and it needs topology to stay
per-object (voxel remesh merges the parts).

## Plan

1. **Foundation and hold keys** (done).
2. **Menus and panels** (done, native UI): native pie menus (Q brushes, A mask, Shift+W hide,
   Alt+W face sets, Z display/mirror/Dyntopo/Multires, S panels) and sidebar
   panels for Brush, Mask/Hide, View/Mode, Deform, Face Sets, Vertex Color,
   Material, Multires, Layers, Extract, Remesh and Boolean. A custom-drawn
   brush wheel and floating panels come after the native version.
3. **Sculpt helpers** (done): Depth Limit, Gravity, Morph, Copy Stamp, named masks
   (add / subtract / intersect), thickness-protect auto-mask, material by
   mask, sculpt several objects together.
4. **Advanced** (done): pivot bend and twist, gizmo for the unmasked part,
   sculpt layers, shape transfer after remesh, boolean layers.

5. **Custom-drawn UI** (done): brush wheel with thumbnails and floating
   panels; the native pies and sidebar panels remain as a fallback.
6. **History** (done): branching snapshot timeline, Blend, Paint Back and the
   Morph Target brush.

## Testing

`tests/test_headless.py` checks registration, keymap, brush switching and the
Multires helpers. `tests/test_tools.py` checks the sculpt helpers on real mesh
data (mask combine modes, Morph, Depth Limit, Copy Stamp, material by mask,
Sculpt Together round trip, pivot bend geometry, sculpt layers, shape
transfer, boolean confirm / cancel). `tests/test_history.py` checks the
snapshot tree and branches, Blend, Paint Back, the Morph Target dab, Jump
after a topology change, the snapshot limit and the Keep in File round trip. `tests/test_custom_ui.py` checks the
brush wheel and floating card layout and hit testing, and that every card
control targets a real operator or property. The GPU drawing itself needs a
real viewport. `tests/test_ui_names.py` draws every panel, pie and popup into
a recording layout and fails on any property, operator argument, panel or menu
name this Blender version doesn't have. Run them with
`blender -b --python tests/<file>` or with the `bpy` module from PyPI
(`pip install bpy==5.2.3`, Python 3.13).

Interactive behaviour needs a real viewport. Manual checklist:

- [ ] Hold C, drag on mesh: mask is painted; release C: previous brush is back.
- [ ] Hold C, Ctrl+drag: mask is removed.
- [ ] Hold C, click mesh: mask edges blur; Ctrl+click sharpens.
- [ ] Hold C, click background: mask inverts; drag background: mask clears.
- [ ] Hold Shift+C, drag box: only the boxed area stays visible.
- [ ] Hold Shift+C, Tab to Lasso / Line, drag: same with those shapes.
- [ ] Hold Shift+C, click a face set: it is isolated; click background: all shown.
- [ ] F1 lists the shortcuts; rebinding in Preferences updates the list.
- [ ] Q, A, Shift+W, Alt+W open their pies and each entry works.
- [ ] Z opens the View / Mode popup; S hides and shows sidebar panels.
- [ ] Every sidebar panel draws, and its ? button shows help.
- [ ] Deform buttons change the mesh; masked areas stay still.
- [ ] Multires Subdivide on a fresh mesh adds the modifier; level − / + work.
- [ ] Depth Limit with Auto on: a heavy Clay stroke stops at Max Height.
- [ ] Gravity Screen ↓ / Into Screen / Drag Direction change how strokes sag.
- [ ] Copy Stamp: sample a detailed area, stamp it on a smooth one.
- [ ] Sculpt Together: combine two meshes, sculpt across both, split back.
- [ ] Y: drop pivots on shoulder and elbow, drag to bend the arm; T twists.
- [ ] Gizmo: mask the body, move / rotate / scale the unmasked arm.
- [ ] Layers: add a layer, sculpt, drag its slider to fade the change.
- [ ] Boolean: add a sphere cutter, Edit to move it, Confirm.
- [ ] Q: wheel shows brush thumbnails; click and release-to-pick both work.
- [ ] History: sculpt 5 strokes, a snapshot appears; Jump back, sculpt, a branch appears.
- [ ] Timeline: thumbnails draw; Blend drag previews live; double-click jumps.
- [ ] Morph Target brush: strokes pull toward the selected snapshot.
- [ ] Keep in File on: save, reopen, the snapshots are still there.
- [ ] S > Floating Panels: cards draw, drag, collapse, ?, ≡ and × work; sliders drag; sculpting under empty space still works.

## License

GPL-3.0-or-later.
