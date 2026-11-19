import type Konva from "konva";
import { useEffect, useMemo, useRef, useState } from "react";
import { Circle, Group, Image as KImage, Layer, Line, Rect, Stage, Text } from "react-konva";
import useImage from "use-image";
import type { DamageType, Point, Region } from "../api/types";
import { DAMAGE } from "../lib/constants";
import { clamp01 } from "../lib/format";

export interface Overlay {
  key: string;
  polygon: Point[];
  color: string;
  label?: string;
  dashed?: boolean;
  fill?: number;
}

interface Props {
  imageUrl: string;
  naturalWidth: number;
  naturalHeight: number;
  regions: Region[];
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  editable?: boolean;
  onPolygonChange?: (id: string, polygon: Point[]) => void;
  drawMode?: boolean;
  drawType?: DamageType;
  onDrawComplete?: (polygon: Point[]) => void;
  onDrawCancel?: () => void;
  grid?: { cols: number; rows: number } | null;
  overlays?: Overlay[];
  maxHeight?: number;
}

const colLabel = (i: number) => {
  let s = "";
  i += 1;
  while (i) {
    const r = (i - 1) % 26;
    s = String.fromCharCode(65 + r) + s;
    i = Math.floor((i - 1) / 26);
  }
  return s;
};

export function AtlasEditor({
  imageUrl,
  naturalWidth,
  naturalHeight,
  regions,
  selectedId,
  onSelect,
  editable,
  onPolygonChange,
  drawMode,
  drawType = "uncertain",
  onDrawComplete,
  onDrawCancel,
  grid,
  overlays = [],
  maxHeight = 640,
}: Props) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [boxW, setBoxW] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [img] = useImage(imageUrl, "anonymous");
  const [draft, setDraft] = useState<Point[]>([]);
  const [cursor, setCursor] = useState<Point | null>(null);
  // Local copy of the polygon being edited so dragging is smooth.
  const [editPoly, setEditPoly] = useState<Point[] | null>(null);

  useEffect(() => {
    const el = boxRef.current;
    if (!el) return;
    setBoxW(el.clientWidth);
    const ro = new ResizeObserver(([e]) => setBoxW(e.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    setEditPoly(null);
  }, [selectedId, regions]);

  useEffect(() => {
    if (!drawMode) setDraft([]);
  }, [drawMode]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && drawMode) {
        setDraft([]);
        onDrawCancel?.();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawMode, onDrawCancel]);

  const fit = Math.max(0.01, Math.min((boxW || 300) / naturalWidth, maxHeight / naturalHeight));
  const scale = fit * zoom;
  const W = naturalWidth * scale;
  const H = naturalHeight * scale;
  const toPx = (p: Point) => [p[0] * W, p[1] * H];
  const flat = (poly: Point[]) => poly.flatMap(toPx);

  const pointer = (e: Konva.KonvaEventObject<MouseEvent | TouchEvent>): Point | null => {
    const pos = e.target.getStage()?.getPointerPosition();
    return pos ? [clamp01(pos.x / W), clamp01(pos.y / H)] : null;
  };

  const handleStageClick = (e: Konva.KonvaEventObject<MouseEvent | TouchEvent>) => {
    if (drawMode) {
      const p = pointer(e);
      if (!p) return;
      if (draft.length >= 3) {
        const [fx, fy] = toPx(draft[0]);
        const [px, py] = toPx(p);
        if (Math.hypot(fx - px, fy - py) < 12) {
          onDrawComplete?.(draft);
          setDraft([]);
          return;
        }
      }
      setDraft([...draft, p]);
      return;
    }
    if (e.target === e.target.getStage() || e.target.name() === "bg") onSelect?.(null);
  };

  const visible = useMemo(() => regions.filter((r) => r.status !== "rejected"), [regions]);
  const selected = visible.find((r) => r.id === selectedId);
  const activePoly = selected ? editPoly ?? selected.polygon : null;
  const fontSize = Math.max(11, Math.min(16, W / 70));

  return (
    <div>
      <div className="toolbar" style={{ marginBottom: 6 }}>
        <button type="button" onClick={() => setZoom((z) => Math.min(4, z * 1.25))} aria-label="تكبير">＋</button>
        <button type="button" onClick={() => setZoom((z) => Math.max(0.5, z / 1.25))} aria-label="تصغير">－</button>
        <button type="button" onClick={() => setZoom(1)}>ملاءمة</button>
        <small className="muted">{Math.round(zoom * 100)}%</small>
      </div>
      {/* The measured box must not grow with the stage, or width feeds back into itself. */}
      <div ref={boxRef} style={{ width: "100%", minWidth: 0 }} />
      <div className="atlas-box" style={{ maxHeight: maxHeight + 20, overflow: "auto", direction: "ltr", maxWidth: "100%" }}>
        <Stage
          width={W}
          height={H}
          onClick={handleStageClick}
          onTap={handleStageClick}
          onMouseMove={(e) => drawMode && setCursor(pointer(e))}
          style={{ cursor: drawMode ? "crosshair" : "default" }}
        >
          <Layer listening>
            {img && <KImage image={img} width={W} height={H} name="bg" />}
          </Layer>
          {grid && (
            <Layer listening={false}>
              {Array.from({ length: grid.cols - 1 }, (_, i) => (
                <Line key={`c${i}`} points={[((i + 1) * W) / grid.cols, 0, ((i + 1) * W) / grid.cols, H]} stroke="rgba(255,255,255,0.55)" strokeWidth={1} dash={[4, 4]} />
              ))}
              {Array.from({ length: grid.rows - 1 }, (_, i) => (
                <Line key={`r${i}`} points={[0, ((i + 1) * H) / grid.rows, W, ((i + 1) * H) / grid.rows]} stroke="rgba(255,255,255,0.55)" strokeWidth={1} dash={[4, 4]} />
              ))}
              {Array.from({ length: grid.cols * grid.rows }, (_, k) => {
                const c = k % grid.cols;
                const r = Math.floor(k / grid.cols);
                return (
                  <Text key={`t${k}`} x={(c * W) / grid.cols + 4} y={(r * H) / grid.rows + 4} text={`${colLabel(c)}${r + 1}`} fontSize={fontSize - 2} fill="rgba(255,255,255,0.85)" shadowColor="black" shadowBlur={2} />
                );
              })}
            </Layer>
          )}
          <Layer>
            {overlays.map((o) => (
              <Group key={o.key} listening={false}>
                <Line points={flat(o.polygon)} closed fill={o.color} opacity={o.fill ?? 0.18} />
                <Line points={flat(o.polygon)} closed stroke={o.color} strokeWidth={2} dash={o.dashed ? [8, 6] : undefined} />
                {o.label && <Text x={toPx(o.polygon[0])[0]} y={toPx(o.polygon[0])[1] - fontSize - 2} text={o.label} fontSize={fontSize} fill="#fff" padding={2} shadowColor="black" shadowBlur={3} />}
              </Group>
            ))}
            {visible.map((r) => {
              const d = DAMAGE[r.damage_type];
              const isSel = r.id === selectedId;
              const poly = isSel && activePoly ? activePoly : r.polygon;
              const [lx, ly] = toPx(poly.reduce((a, p) => (p[1] < a[1] ? p : a), poly[0]));
              return (
                <Group key={r.id}>
                  <Line
                    points={flat(poly)}
                    closed
                    fill={d.color}
                    opacity={isSel ? 0.38 : r.status === "approved" ? 0.22 : 0.3}
                    onClick={(e) => {
                      if (drawMode) return;
                      e.cancelBubble = true;
                      onSelect?.(r.id);
                    }}
                    onTap={(e) => {
                      if (drawMode) return;
                      e.cancelBubble = true;
                      onSelect?.(r.id);
                    }}
                    draggable={editable && isSel && !drawMode}
                    onDragEnd={(e) => {
                      const dx = e.target.x() / W;
                      const dy = e.target.y() / H;
                      e.target.position({ x: 0, y: 0 });
                      const moved = poly.map(([x, y]) => [clamp01(x + dx), clamp01(y + dy)] as Point);
                      setEditPoly(moved);
                      onPolygonChange?.(r.id, moved);
                    }}
                  />
                  <Line
                    points={flat(poly)}
                    closed
                    listening={false}
                    stroke={isSel ? "#fff" : d.color}
                    strokeWidth={isSel ? 3 : 2}
                    dash={d.dashed || r.low_confidence ? [8, 6] : undefined}
                  />
                  <Rect x={lx} y={ly - fontSize - 6} width={fontSize * 2.4} height={fontSize + 4} fill={d.color} cornerRadius={3} listening={false} />
                  <Text x={lx + 3} y={ly - fontSize - 4} text={`R${r.index}`} fontSize={fontSize} fill="#fff" fontStyle="bold" listening={false} />
                </Group>
              );
            })}
            {editable && selected && activePoly && !drawMode &&
              activePoly.map((p, i) => (
                <Circle
                  key={i}
                  x={p[0] * W}
                  y={p[1] * H}
                  radius={6}
                  fill="#fff"
                  stroke={DAMAGE[selected.damage_type].color}
                  strokeWidth={2}
                  draggable
                  onDragMove={(e) => {
                    const next = [...activePoly];
                    next[i] = [clamp01(e.target.x() / W), clamp01(e.target.y() / H)];
                    setEditPoly(next);
                  }}
                  onDragEnd={() => editPoly && onPolygonChange?.(selected.id, editPoly)}
                  onDblClick={() => {
                    if (activePoly.length <= 3) return;
                    const next = activePoly.filter((_, k) => k !== i);
                    setEditPoly(next);
                    onPolygonChange?.(selected.id, next);
                  }}
                />
              ))}
            {drawMode && draft.length > 0 && (
              <Group listening={false}>
                <Line points={flat(cursor ? [...draft, cursor] : draft)} stroke={DAMAGE[drawType].color} strokeWidth={2} dash={[6, 4]} />
                {draft.map((p, i) => (
                  <Circle key={i} x={p[0] * W} y={p[1] * H} radius={i === 0 ? 7 : 4} fill={i === 0 ? "#fff" : DAMAGE[drawType].color} stroke={DAMAGE[drawType].color} />
                ))}
              </Group>
            )}
          </Layer>
        </Stage>
        {drawMode && (
          <div className="atlas-hint">
            انقر لإضافة نقاط، ثم انقر على النقطة الأولى لإغلاق المنطقة. Esc للإلغاء.
          </div>
        )}
        {editable && selected && !drawMode && (
          <div className="atlas-hint">اسحب النقاط لتعديل الحدود، أو اسحب المنطقة لنقلها. نقر مزدوج على نقطة يحذفها.</div>
        )}
      </div>
    </div>
  );
}
