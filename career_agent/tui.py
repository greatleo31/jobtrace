from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, ListItem, ListView, RichLog, Static

from .models import JobRecord
from .store import CareerStore


class JobItem(ListItem):
    def __init__(self, job: JobRecord) -> None:
        super().__init__(Static(f"{job.title}\n{job.company} · {job.location}"))
        self.job = job


class JobTraceApp(App[None]):
    CSS = """
    #workspace { height: 1fr; }
    #jobs { width: 38%; border-right: solid $primary; }
    #detail { width: 62%; padding: 1 2; }
    #query { dock: bottom; }
    """
    BINDINGS = [("q", "quit", "退出"), ("r", "reload", "刷新")]

    def __init__(self, database: str | Path) -> None:
        super().__init__()
        self.store = CareerStore(database)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            yield ListView(id="jobs")
            with Vertical(id="detail"):
                yield Static("选择岗位查看详情", id="summary")
                yield RichLog(id="trace", wrap=True, markup=True)
        yield Input(placeholder="输入关键词筛选岗位，或输入 /all 查看全部", id="query")
        yield Footer()

    def on_mount(self) -> None:
        self.action_reload()

    def action_reload(self) -> None:
        self._show_jobs(self.store.list_jobs())

    def _show_jobs(self, jobs: list[JobRecord]) -> None:
        view = self.query_one("#jobs", ListView)
        view.clear()
        view.extend(JobItem(job) for job in jobs)
        self.query_one("#trace", RichLog).write(f"载入 {len(jobs)} 个岗位")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not isinstance(event.item, JobItem):
            return
        job = event.item.job
        self.query_one("#summary", Static).update(
            f"[b]{job.title}[/b]\n{job.company} · {job.location} · {job.salary or '薪资未知'}\n\n"
            f"技能：{', '.join(job.skills) or '未提取'}\n\n{job.description or '暂无 JD'}"
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        jobs = self.store.list_jobs() if query == "/all" else self.store.search_jobs(query)
        self._show_jobs(jobs)
        event.input.clear()

    def on_unmount(self) -> None:
        self.store.close()


def run_tui(database: str | Path) -> None:
    JobTraceApp(database).run()
