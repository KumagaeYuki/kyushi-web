#!/usr/bin/env python3
"""Generate MkDocs pages from the kyushi-ronbun dataset."""

from __future__ import annotations

import html
import re
from urllib.parse import quote
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, TypedDict, Tuple

import yaml


SUBJECT_NAMES: Dict[str, str] = {
    "kenpo": "憲法",
    "keiho": "刑法",
    "keisoho": "刑事訴訟法",
    "minsoho": "民事訴訟法",
    "minpo": "民法",
    "shoho": "商法",
}

ERA_NAMES = {"s": "昭和", "h": "平成"}
SUBJECT_ORDER = ["憲法", "民法", "商法", "刑法", "民事訴訟法", "刑事訴訟法"]

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "kyushi-ronbun"
DOCS_DIR = ROOT / "docs"


class Question(TypedDict):
    subject: str
    subject_label: str
    year: int
    era_code: str
    qnum: int
    text: str
    slug: str
    source: str
    tags: List[str]


def parse_filename(path: Path) -> Question:
    match = re.match(
        r"kyushi_(?P<subject>[a-z]+)_(?P<year>\d{4})_(?P<era>[sh]\d{2})_q(?P<qnum>\d+)\.txt$",
        path.name,
    )
    if not match:
        raise ValueError(f"Unexpected filename format: {path.name}")

    subject_code = match.group("subject")
    subject_label = SUBJECT_NAMES.get(subject_code, subject_code)
    year = int(match.group("year"))
    era_code = match.group("era")
    qnum = int(match.group("qnum"))
    slug = f"{year}_{era_code}_q{qnum}.md"

    return {
        "subject": subject_code,
        "subject_label": subject_label,
        "year": year,
        "era_code": era_code,
        "qnum": qnum,
        "text": path.read_text(encoding="utf-8").strip("\n"),
        "slug": slug,
        "source": f"kyushi-ronbun/{subject_code}/{path.name}",
        "tags": [],
    }


def era_label(code: str, suffix: str = "年") -> str:
    era = ERA_NAMES.get(code[0], code[0])
    number = int(code[1:])
    return f"{era}{number}{suffix}"


def ensure_empty_subject_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def format_blockquote(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.strip():
            lines.append(f"> {line}")
        else:
            lines.append(">")
    return "\n".join(lines).rstrip()


def read_existing_tags_and_memo(path: Path) -> Tuple[List[str], str]:
    if not path.exists():
        return [], "_ここにメモを書く_"

    content = path.read_text(encoding="utf-8")
    tags: List[str] = []
    memo = "_ここにメモを書く_"

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1])
                if isinstance(meta, dict) and isinstance(meta.get("tags"), list):
                    tags = [str(t) for t in meta.get("tags", [])]
            except Exception:
                tags = []
    memo_match = re.search(r"## メモ\s*\n(.*)", content, re.S)
    if memo_match:
        memo_body = memo_match.group(1).rstrip()
        if memo_body:
            memo = memo_body

    return tags, memo


def write_question_page(target: Path, q: Question) -> None:
    title = f"{era_label(q['era_code'], '年度')} 旧司法試験 論文式試験問題 {q['subject_label']} 第{q['qnum']}問"
    blockquote = format_blockquote(q["text"])
    existing_tags, memo = read_existing_tags_and_memo(target)
    q["tags"] = existing_tags
    frontmatter = ["---", f"title: {title}"]
    if existing_tags:
        frontmatter.append("tags:")
        frontmatter.extend([f"  - {t}" for t in existing_tags])
    else:
        frontmatter.append("tags: []")
    frontmatter.append("---")

    content = "\n".join(
        frontmatter
        + [
            "",
            f"# {title}",
            "",
            "## 問題",
            "",
            blockquote,
            "",
            "## メモ",
            "",
            memo,
            "",
        ]
    )
    target.write_text(content, encoding="utf-8")


def write_subject_index(subject_dir: Path, subject_code: str, questions: List[Question]) -> None:
    subject_label = SUBJECT_NAMES.get(subject_code, subject_code)
    by_year: Dict[int, List[Question]] = defaultdict(list)
    for q in questions:
        by_year[q["year"]].append(q)

    lines = [
        f"# {subject_label}",
        "",
        "| 年度 | 問題 |",
        "| --- | --- |",
    ]

    for year in sorted(by_year.keys(), reverse=True):
        era = era_label(by_year[year][0]["era_code"], "年度")
        q_links = " / ".join(
            f"[第{q['qnum']}問]({q['slug']})"
            for q in sorted(by_year[year], key=lambda item: item["qnum"])
        )
        lines.append(f"| {era}（{year}年度） | {q_links} |")

    subject_index = subject_dir / "index.md"
    subject_index.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_home(all_questions: List[Question]) -> None:
    def subject_key(label: str) -> tuple:
        try:
            return (SUBJECT_ORDER.index(label), "")
        except ValueError:
            return (len(SUBJECT_ORDER), label)

    subjects = sorted({q["subject_label"] for q in all_questions}, key=subject_key)
    year_labels: Dict[int, str] = {}
    for q in all_questions:
        if q["year"] not in year_labels:
            year_labels[q["year"]] = era_label(q["era_code"], "年度")
    years = sorted(year_labels.keys(), reverse=True)
    header = [
        "# 旧司法試験 論文式試験問題",
        "",
        "科目・年度・問題番号で絞り込み、列ヘッダでソートできます。キーワードは空白区切りでAND検索です。",
        "",
        '<div class="filters">',
        '  <label>科目 <select id="filter-subject" autocomplete="off"><option value="" selected>すべて</option>'
        + "".join(f'<option value="{s}">{s}</option>' for s in subjects)
        + "</select></label>",
        '  <label>年度 <select id="filter-year" autocomplete="off"><option value="">すべて</option>'
        + "".join(
            f'<option value="{year}">{year_labels[year]}（{year}年度）</option>'
            for year in years
        )
        + "</select></label>",
        '  <label>問題 <select id="filter-q" autocomplete="off"><option value="">すべて</option><option value="1">第1問</option><option value="2">第2問</option><option value="3">第3問</option><option value="4">第4問</option></select></label>',
        '  <label>検索 <input id="filter-text" autocomplete="off" type="search" placeholder="例: 共同正犯 共謀 240条" aria-label="キーワードで絞り込み" class="md-input"></label>',
        '  <button id="clear-filters" type="button" class="clear-btn">条件をクリア</button>',
        "</div>",
        '<div id="results-count" class="results-count"></div>',
        "",
        '<table id="questions">',
        "  <thead>",
        '    <tr><th>科目</th><th data-sort="year">年度</th><th data-sort="q">問題</th><th>概要</th><th>タグ</th></tr>',
        "  </thead>",
        "  <tbody>",
    ]

    rows: List[str] = []
    sorted_questions = sorted(
        all_questions,
        key=lambda q: (
            subject_key(q["subject_label"]),
            -q["year"],
            q["qnum"],
        ),
    )
    for q in sorted_questions:
        search_text = " ".join(
            [
                q["subject_label"],
                era_label(q["era_code"], "年度"),
                f"第{q['qnum']}問",
                str(q["year"]),
                q["text"].replace("\n", " "),
                " ".join(q.get("tags", [])),
            ]
        ).lower()
        snippet_text = q["text"].replace("\n", " ")
        if len(snippet_text) > 70:
            snippet_text = snippet_text[:70] + "…"
        snippet_html = html.escape(snippet_text)
        tags_list = q.get("tags", [])
        tags_html = (
            " ".join(
                f'<button class="tag-link" type="button" data-tag="{html.escape(t)}">{html.escape(t)}</button>'
                for t in tags_list
            )
            if tags_list
            else "—"
        )
        row = (
            f'    <tr data-search="{html.escape(search_text)}" '
            f'data-subject="{q["subject_label"]}" '
            f'data-year="{q["year"]}" '
            f'data-era="{era_label(q["era_code"], "年度")}" '
            f'data-q="{q["qnum"]}">'
            f"<td>{q['subject_label']}</td>"
            f"<td>{era_label(q['era_code'], '年度')}（{q['year']}年度）</td>"
            f'<td><a class="problem-link" href="./{q["subject"]}/{q["slug"].replace(".md","")}/">第{q["qnum"]}問</a></td>'
            f'<td class="snippet-cell" data-snippet="{snippet_html}">{snippet_html}</td>'
            f'<td class="tags-cell" data-tags="{html.escape("|||".join(tags_list))}">{tags_html}</td>'
            "</tr>"
        )
        rows.append(row)

    script = r"""
<style>
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin: 0 0 1rem 0;
}
.clear-btn {
  padding: 0.35rem 0.75rem;
  border-radius: 0.4rem;
  border: 1px solid var(--md-sys-color-outline-variant, #d0d0d0);
  background: var(--md-sys-color-surface-container-high, #f6f6f6);
  cursor: pointer;
}
.clear-btn:hover {
  background: var(--md-sys-color-surface-container-highest, #ededed);
}
.results-count {
  margin: 0 0 0.5rem 0;
  font-size: 0.95rem;
  color: #444;
}
.filters label {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-weight: 600;
}
#questions th[data-sort] {
  cursor: pointer;
  position: relative;
  padding-right: 1rem;
}
#questions th[data-sort]::after {
  content: "↕";
  position: absolute;
  right: 0.25rem;
  font-size: 1.05em;
  color: var(--md-sys-color-on-surface-variant, #444);
}
.col-link {
  width: 1.2rem;
  text-align: center;
  vertical-align: middle;
}
.open-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.2rem;
  height: 1.2rem;
  font-size: 1rem;
  transition: transform 0.1s ease, color 0.1s ease;
}
.open-link:hover {
  color: var(--md-sys-color-primary, #3949ab);
  transform: translateY(-1px);
}
.problem-link {
  text-decoration: underline;
}
.tag-link {
  display: inline-block;
  padding: 0.05rem 0.25rem;
  margin: 0 0.08rem 0.08rem 0;
  border-radius: 0.35rem;
  border: 1px solid var(--md-sys-color-outline-variant, #dcdcdc);
  background: var(--md-sys-color-surface-container-high, #f6f6f6);
  font-size: 0.75rem;
  cursor: pointer;
}
.tag-link:hover {
  background: var(--md-sys-color-surface-container-highest, #ededed);
  border-color: var(--md-sys-color-primary, #3949ab);
}
.snippet-cell {
  max-width: 24rem;
}
mark.hl {
  background: #fff3b0;
  padding: 0 0.1rem;
  border-radius: 0.15rem;
}
.tag-link {
  display: inline-block;
  padding: 0.05rem 0.25rem;
  margin: 0 0.08rem 0.08rem 0;
  border-radius: 0.35rem;
  border: 1px solid var(--md-sys-color-outline-variant, #dcdcdc);
  background: var(--md-sys-color-surface-container-high, #f6f6f6);
  font-size: 0.75rem;
  cursor: pointer;
}
.tag-link:hover {
  background: var(--md-sys-color-surface-container-highest, #ededed);
  border-color: var(--md-sys-color-primary, #3949ab);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
<script>
(() => {
  const subject = document.getElementById('filter-subject');
  const year = document.getElementById('filter-year');
  const qnum = document.getElementById('filter-q');
  const text = document.getElementById('filter-text');
  const resultsCount = document.getElementById('results-count');
  const clearBtn = document.getElementById('clear-filters');
  const rows = Array.from(document.querySelectorAll('#questions tbody tr'));
  const tbody = document.querySelector('#questions tbody');
  const resetSelect = (el) => {
    if (!el) return;
    el.selectedIndex = 0;
    el.value = '';
  };
  const escapeHtml = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const highlightText = (base, tokens) => {
    if (!tokens.length) return base;
    return tokens.reduce((acc, tok) => acc.replace(new RegExp(`(${escapeRegex(tok)})`, 'gi'), '<mark class="hl">$1</mark>'), base);
  };
  const applyParams = () => {
    const params = new URLSearchParams(window.location.search);
    resetSelect(subject);
    resetSelect(year);
    resetSelect(qnum);
    if (text) text.value = '';
    if (params.has('subject') && subject) {
      subject.value = params.get('subject');
    }
    if (params.has('year') && year) {
      year.value = params.get('year');
    }
    if (params.has('q') && qnum) {
      qnum.value = params.get('q');
    }
    if (params.has('text') && text) {
      text.value = params.get('text');
    }
    // if URLにパラメータがないのにブラウザが値を復元した場合は強制的に初期化
    if (!window.location.search) {
      resetSelect(subject);
      resetSelect(year);
      resetSelect(qnum);
      if (text) text.value = '';
    }
    // 選択状態を確実に先頭に揃える
    const clearSelectedAttr = (el) => {
      if (!el) return;
      Array.from(el.options).forEach(opt => opt.removeAttribute('selected'));
      el.options[0]?.setAttribute('selected', 'selected');
    };
    clearSelectedAttr(subject);
    clearSelectedAttr(year);
    clearSelectedAttr(qnum);
  };

  const applyFilters = () => {
    const s = (subject?.value || '').trim();
    const y = (year?.value || '').trim().toLowerCase();
    const q = (qnum?.value || '').trim().toLowerCase();
    const t = (text?.value || '').trim().toLowerCase();
    const tokens = t ? t.split(/\s+/).filter(Boolean) : [];

    rows.forEach(row => {
      const okSubject = !s || row.dataset.subject === s;
      const hayYear = ((row.dataset.year || '') + ' ' + (row.dataset.era || '')).toLowerCase();
      const okYear = !y || hayYear.includes(y);
      const hayQ = (`第${row.dataset.q}問`).toLowerCase();
      const okQ = !q || hayQ.includes(q);
      const hayAll = (row.dataset.search || '').toLowerCase();
      const okText = !tokens.length || tokens.every(tok => hayAll.includes(tok));
      row.hidden = !(okSubject && okYear && okQ && okText);

      // highlight snippet and tags
      const snippetCell = row.querySelector('.snippet-cell');
      if (snippetCell) {
        const base = snippetCell.dataset.snippet || '';
        snippetCell.innerHTML = tokens.length ? highlightText(base, tokens) : base;
      }
      const tagsCell = row.querySelector('.tags-cell');
      if (tagsCell) {
        const rawTags = tagsCell.dataset.tags || '';
        if (!rawTags) {
          tagsCell.innerHTML = "—";
        } else {
          const list = rawTags.split("|||").filter(Boolean);
          tagsCell.innerHTML = list
            .map(t => {
              const shown = tokens.length ? highlightText(escapeHtml(t), tokens) : escapeHtml(t);
              return `<button class="tag-link" type="button" data-tag="${escapeHtml(t)}">${shown}</button>`;
            })
            .join(" ");
        }
      }
    });
    if (resultsCount) {
      const visible = rows.filter(row => !row.hidden).length;
      resultsCount.textContent = `表示: ${visible} 問 / 全 ${rows.length} 問`;
    }
    attachTagHandlers();
  };

  [subject, year, qnum, text].forEach(el => {
    el?.addEventListener('input', applyFilters);
  });

  const headers = Array.from(document.querySelectorAll('#questions thead th[data-sort]'));
  let sortState = { key: 'subject', dir: 'asc' };

  const compare = (a, b, key) => {
    if (key === 'year') {
      return Number(a.dataset.year) - Number(b.dataset.year);
    }
    if (key === 'q') {
      return Number(a.dataset.q) - Number(b.dataset.q);
    }
    return (a.dataset[key] || '').localeCompare(b.dataset[key] || ''); 
  };

  headers.forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      const dir = sortState.key === key && sortState.dir === 'asc' ? 'desc' : 'asc';
      sortState = { key, dir };
      const sorted = [...rows].sort((a, b) => {
        const base = compare(a, b, key);
        return dir === 'asc' ? base : -base;
      });
      sorted.forEach(row => tbody.appendChild(row));
      applyFilters();
    });
  });

  const attachTagHandlers = () => {
    const buttons = Array.from(document.querySelectorAll('.tag-link'));
    buttons.forEach(btn => {
      btn.addEventListener('click', () => {
        const tag = btn.dataset.tag || btn.textContent.trim();
        if (!tag || !text) return;
        const tokens = (text.value || '').trim().split(/\s+/).filter(Boolean);
        const next = Array.from(new Set([...tokens, tag]));
        text.value = next.join(' ');
        applyFilters();
      });
    });
  };

  const initFilters = () => {
    applyParams();
    applyFilters();
    attachTagHandlers();
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      initFilters();
      requestAnimationFrame(initFilters);
    });
  } else {
    initFilters();
    requestAnimationFrame(initFilters);
  }
  clearBtn?.addEventListener('click', () => {
    resetSelect(subject);
    resetSelect(year);
    resetSelect(qnum);
    if (text) text.value = '';
    applyFilters();
  });
})();
</script>
""".strip()

    footer = [
        "  </tbody>",
        "</table>",
        "",
        script,
        "",
    ]

    content = "\n".join(header + rows + footer)
    (DOCS_DIR / "index.md").write_text(content, encoding="utf-8")


def main() -> None:
    if not DATA_DIR.exists():
        raise SystemExit("Dataset directory kyushi-ronbun not found.")

    DOCS_DIR.mkdir(exist_ok=True)
    all_questions: List[Question] = []

    for subject_dir in DATA_DIR.iterdir():
        if not subject_dir.is_dir():
            continue
        subject_code = subject_dir.name
        output_dir = DOCS_DIR / subject_code
        ensure_empty_subject_dir(output_dir)

        questions: List[Question] = []
        for txt_file in subject_dir.glob("kyushi_*.txt"):
            question = parse_filename(txt_file)
            questions.append(question)
            all_questions.append(question)
            write_question_page(output_dir / question["slug"], question)

    write_home(all_questions)

if __name__ == "__main__":
    main()
