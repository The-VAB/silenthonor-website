import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get, post, put, del } from "@/lib/api";
import type { CourseRow, CourseDetail, Lesson } from "@/lib/types";
import { Card, Badge, Spinner, ErrorState, Empty } from "@/components/ui";
import { Modal } from "@/components/Modal";
import { useToast } from "@/components/toast";

const LESSON_ICON: Record<string, string> = { video: "▶", text: "📄", resource: "💾" };

interface LessonCtx {
  lessonId: string | null;
  moduleId: string | null;
  lesson?: Lesson;
}
interface CourseForm {
  title: string;
  description: string;
  category: string;
  status: string;
  thumbnail: string;
}

export default function Courses() {
  const [sel, setSel] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [lessonCtx, setLessonCtx] = useState<LessonCtx | null>(null);
  const [courseModal, setCourseModal] = useState<{ form: CourseForm; isNew: boolean } | null>(null);
  const toast = useToast();
  const qc = useQueryClient();

  const listQ = useQuery<CourseRow[]>({
    queryKey: ["admin", "courses"],
    queryFn: () => get<CourseRow[]>("/api/admin/courses"),
  });
  const courseQ = useQuery<CourseDetail>({
    queryKey: ["admin", "course", sel],
    queryFn: () => get<CourseDetail>(`/api/admin/courses/${sel}`),
    enabled: !!sel,
  });

  const rows = useMemo(() => {
    const all = listQ.data ?? [];
    const s = q.toLowerCase();
    return s ? all.filter((c) => c.title.toLowerCase().includes(s)) : all;
  }, [listQ.data, q]);

  const reloadList = () => qc.invalidateQueries({ queryKey: ["admin", "courses"] });
  const reloadCourse = () => qc.invalidateQueries({ queryKey: ["admin", "course", sel] });

  async function wrap(fn: () => Promise<unknown>, ok: string, after?: () => void) {
    try {
      await fn();
      toast(ok, "success");
      after?.();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error", "error");
    }
  }

  async function saveCourse(form: CourseForm) {
    const body = { title: form.title.trim(), description: form.description, category: form.category, status: form.status, thumbnail: form.thumbnail || null };
    if (!body.title) {
      toast("Title required", "error");
      return;
    }
    const isNew = courseModal?.isNew ?? true;
    await wrap(
      () => (isNew || !sel ? post("/api/admin/courses", body) : put(`/api/admin/courses/${sel}`, body)),
      "Course saved",
      () => { setCourseModal(null); reloadList(); reloadCourse(); }
    );
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Courses</h1>
          <p>Build and publish the curriculum members work through.</p>
        </div>
        <button className="btn primary" onClick={() => setCourseModal({ form: { title: "", description: "", category: "", status: "draft", thumbnail: "" }, isNew: true })}>
          + New Course
        </button>
      </div>

      {listQ.isLoading ? (
        <Spinner />
      ) : listQ.isError ? (
        <ErrorState error={listQ.error} retry={() => listQ.refetch()} />
      ) : (
        <div className="builder">
          <Card>
            <div style={{ padding: 12 }}>
              <input placeholder="Search courses…" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: "100%" }} />
            </div>
            <div style={{ borderTop: "1px solid var(--line)" }}>
              {rows.length === 0 ? (
                <Empty>No courses yet.</Empty>
              ) : (
                rows.map((c) => (
                  <div key={c.id} className={"course-list-item" + (c.id === sel ? " active" : "")} onClick={() => setSel(c.id)}>
                    <div className="t">{c.title}</div>
                    <div className="m">
                      {c.category || "Uncategorized"} · {c.total_lessons ?? 0} lessons
                      <Badge tone={c.status === "published" ? "ok" : "muted"}>{c.status}</Badge>
                    </div>
                  </div>
                ))
              )}
            </div>
          </Card>

          <Card>
            <div className="card-pad">
              {!sel ? (
                <Empty>Select a course to edit, or create a new one.</Empty>
              ) : courseQ.isLoading || !courseQ.data ? (
                <Spinner />
              ) : (
                <CourseEditor
                  c={courseQ.data}
                  onEditDetails={() =>
                    setCourseModal({
                      form: {
                        title: courseQ.data!.title,
                        description: courseQ.data!.description ?? "",
                        category: courseQ.data!.category ?? "",
                        status: courseQ.data!.status,
                        thumbnail: courseQ.data!.thumbnail ?? "",
                      },
                      isNew: false,
                    })
                  }
                  onDelete={() => {
                    if (!window.confirm(`Delete course "${courseQ.data!.title}" and all its content?`)) return;
                    wrap(() => del(`/api/admin/courses/${sel}`), "Course deleted", () => { setSel(null); reloadList(); });
                  }}
                  onToggle={() =>
                    wrap(
                      () => put(`/api/admin/courses/${sel}`, { title: courseQ.data!.title, description: courseQ.data!.description, category: courseQ.data!.category, status: courseQ.data!.status === "published" ? "draft" : "published" }),
                      "Status updated",
                      () => { reloadCourse(); reloadList(); }
                    )
                  }
                  onAddModule={() => wrap(() => post(`/api/admin/courses/${sel}/modules`, { title: "New Module", order: 0 }), "Module added", reloadCourse)}
                  onRenameModule={(mid, title) => wrap(() => put(`/api/admin/modules/${mid}`, { title }), "Module renamed", reloadCourse)}
                  onDeleteModule={(mid) => {
                    if (!window.confirm("Delete this module and all its lessons?")) return;
                    wrap(() => del(`/api/admin/modules/${mid}`), "Module deleted", reloadCourse);
                  }}
                  onAddLesson={(mid) => setLessonCtx({ lessonId: null, moduleId: mid })}
                  onEditLesson={(l, mid) => setLessonCtx({ lessonId: l.id, moduleId: mid, lesson: l })}
                  onDeleteLesson={(lid) => {
                    if (!window.confirm("Delete this lesson?")) return;
                    wrap(() => del(`/api/admin/lessons/${lid}`), "Lesson deleted", reloadCourse);
                  }}
                />
              )}
            </div>
          </Card>
        </div>
      )}

      {courseModal && (
        <CourseModal
          initial={courseModal.form}
          isNew={courseModal.isNew}
          onClose={() => setCourseModal(null)}
          onSave={saveCourse}
        />
      )}

      {lessonCtx && sel && (
        <LessonModal
          ctx={lessonCtx}
          courseId={sel}
          onClose={() => setLessonCtx(null)}
          onSaved={() => { setLessonCtx(null); reloadCourse(); }}
        />
      )}
    </>
  );
}

function CourseEditor(props: {
  c: CourseDetail;
  onEditDetails: () => void;
  onDelete: () => void;
  onToggle: () => void;
  onAddModule: () => void;
  onRenameModule: (mid: string, title: string) => void;
  onDeleteModule: (mid: string) => void;
  onAddLesson: (mid: string | null) => void;
  onEditLesson: (l: Lesson, mid: string | null) => void;
  onDeleteLesson: (lid: string) => void;
}) {
  const { c } = props;
  const LessonRow = ({ l, mid }: { l: Lesson; mid: string | null }) => (
    <div className="lesson-row">
      <span className="lesson-ico">{LESSON_ICON[l.lesson_type ?? "text"] ?? "📄"}</span>
      <span className="lt">{l.title}</span>
      <span className="ltype">{l.lesson_type ?? "text"}{l.duration ? ` · ${l.duration}` : ""}</span>
      <button className="btn sm" onClick={() => props.onEditLesson(l, mid)}>Edit</button>
      <button className="btn sm" style={{ color: "var(--danger)" }} onClick={() => props.onDeleteLesson(l.id)}>×</button>
    </div>
  );

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ fontSize: 20, textTransform: "uppercase" }}>{c.title}</h3>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn sm" onClick={props.onEditDetails}>Edit Details</button>
          <button className="btn sm" style={{ color: "var(--danger)" }} onClick={props.onDelete}>Delete</button>
        </div>
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 18 }}>
        <Badge tone={c.status === "published" ? "ok" : "muted"}>{c.status}</Badge>
        <span className="cell-sub">{c.category || "No category"}</span>
        <button className="btn sm" onClick={props.onToggle}>
          {c.status === "published" ? "Unpublish" : "Publish"}
        </button>
      </div>

      {(c.modules ?? []).map((m) => (
        <div className="module-block" key={m.id}>
          <div className="module-header">
            <input defaultValue={m.title} onBlur={(e) => e.target.value.trim() && e.target.value !== m.title && props.onRenameModule(m.id, e.target.value.trim())} />
            <button className="btn sm" onClick={() => props.onAddLesson(m.id)}>+ Lesson</button>
            <button className="btn sm" style={{ color: "var(--danger)" }} onClick={() => props.onDeleteModule(m.id)}>Delete</button>
          </div>
          <div className="module-body">
            {(m.lessons ?? []).length === 0 ? (
              <div className="cell-sub" style={{ padding: 4 }}>No lessons yet.</div>
            ) : (
              m.lessons!.map((l) => <LessonRow key={l.id} l={l} mid={m.id} />)
            )}
          </div>
        </div>
      ))}

      {(c.flat_lessons ?? []).length > 0 && (
        <>
          <div className="section-label">Unassigned Lessons</div>
          {c.flat_lessons!.map((l) => <LessonRow key={l.id} l={l} mid={null} />)}
        </>
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
        <button className="btn primary sm" onClick={props.onAddModule}>+ Add Module</button>
        <button className="btn sm" onClick={() => props.onAddLesson(null)}>+ Add Lesson (no module)</button>
      </div>
    </>
  );
}

function CourseModal({ initial, isNew, onClose, onSave }: { initial: CourseForm; isNew: boolean; onClose: () => void; onSave: (f: CourseForm) => void }) {
  const [f, setF] = useState<CourseForm>(initial);
  return (
    <Modal
      title={isNew ? "New Course" : "Edit Course"}
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={() => onSave(f)}>Save</button>
        </>
      }
    >
      <div className="field-row">
        <div className="field-label">Title</div>
        <input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} style={{ width: "100%" }} />
      </div>
      <div className="form-grid-2">
        <div className="field-row">
          <div className="field-label">Category</div>
          <input value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })} style={{ width: "100%" }} />
        </div>
        <div className="field-row">
          <div className="field-label">Status</div>
          <select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} style={{ width: "100%" }}>
            <option value="draft">Draft</option>
            <option value="published">Published</option>
          </select>
        </div>
      </div>
      <div className="field-row">
        <div className="field-label">Thumbnail URL</div>
        <input value={f.thumbnail} onChange={(e) => setF({ ...f, thumbnail: e.target.value })} style={{ width: "100%" }} />
      </div>
      <div className="field-row">
        <div className="field-label">Description</div>
        <textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} rows={3} style={{ width: "100%" }} />
      </div>
    </Modal>
  );
}

function LessonModal({ ctx, courseId, onClose, onSaved }: { ctx: LessonCtx; courseId: string; onClose: () => void; onSaved: () => void }) {
  const l = ctx.lesson;
  const [title, setTitle] = useState(l?.title ?? "");
  const [type, setType] = useState<string>(l?.lesson_type ?? "text");
  const [content, setContent] = useState(l?.content ?? "");
  const [videoUrl, setVideoUrl] = useState(l?.video_url ?? "");
  const [resourceUrl, setResourceUrl] = useState(l?.resource_url ?? "");
  const [duration, setDuration] = useState(l?.duration ?? "");
  const toast = useToast();

  async function save() {
    if (!title.trim()) {
      toast("Title required", "error");
      return;
    }
    const data = {
      title: title.trim(),
      content,
      lesson_type: type,
      video_url: videoUrl || null,
      resource_url: resourceUrl || null,
      duration: duration || null,
      order: 0,
    };
    try {
      const { lessonId, moduleId } = ctx;
      if (lessonId) {
        if (moduleId) await put(`/api/admin/modules/${moduleId}/lessons/${lessonId}`, data);
        else await put(`/api/admin/lessons/${lessonId}`, { ...data, course_id: courseId });
      } else {
        if (moduleId) await post(`/api/admin/modules/${moduleId}/lessons`, data);
        else await post("/api/admin/lessons", { ...data, course_id: courseId });
      }
      toast("Lesson saved", "success");
      onSaved();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Error", "error");
    }
  }

  return (
    <Modal
      title={ctx.lessonId ? "Edit Lesson" : "Add Lesson"}
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={save}>Save Lesson</button>
        </>
      }
    >
      <div className="field-row">
        <div className="field-label">Title</div>
        <input value={title} onChange={(e) => setTitle(e.target.value)} style={{ width: "100%" }} />
      </div>
      <div className="form-grid-2">
        <div className="field-row">
          <div className="field-label">Type</div>
          <select value={type} onChange={(e) => setType(e.target.value)} style={{ width: "100%" }}>
            <option value="text">Text</option>
            <option value="video">Video</option>
            <option value="resource">Resource</option>
          </select>
        </div>
        <div className="field-row">
          <div className="field-label">Duration (optional)</div>
          <input value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="e.g. 8 min" style={{ width: "100%" }} />
        </div>
      </div>
      {type === "video" && (
        <div className="field-row">
          <div className="field-label">Video URL</div>
          <input value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} style={{ width: "100%" }} />
        </div>
      )}
      {type === "resource" && (
        <div className="field-row">
          <div className="field-label">Resource URL</div>
          <input value={resourceUrl} onChange={(e) => setResourceUrl(e.target.value)} style={{ width: "100%" }} />
        </div>
      )}
      {type === "text" && (
        <div className="field-row">
          <div className="field-label">Content</div>
          <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={6} style={{ width: "100%" }} />
        </div>
      )}
    </Modal>
  );
}
