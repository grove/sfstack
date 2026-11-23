"""Offline checks for the product's curated Markdown entry points."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]\n]+\]\(([^)\s]+)\)")
FENCE = re.compile(r"^\s*(\x60{3,}|~{3,})")
HEADING = re.compile(r"^#{1,6} (.+?)\s*$", re.MULTILINE)
ANCHOR = re.compile(r'<a\s+(?:id|name)="([^"]+)"')


def prose(content):
    """Exclude fenced examples: example paths are not navigation links."""
    lines = []
    marker = None
    for line in content.splitlines():
        fence = FENCE.match(line)
        if fence:
            kind = fence.group(1)[0]
            if marker is None:
                marker = kind
            elif marker == kind:
                marker = None
            continue
        if marker is None:
            lines.append(line)
    return "\n".join(lines)


def anchors(content):
    body = prose(content)
    result = set(ANCHOR.findall(body))
    seen = {}
    for title in HEADING.findall(body):
        slug = re.sub(r"[^\w-]", "", title.lower().replace(" ", "-"))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(slug if not count else f"{slug}-{count}")
    return result


PAGES = (
    "README.md",
    "docs/README.md",
    "docs/how-to/run-software-factory.md",
    "docs/how-to/run-github.md",
    "docs/how-to/issue-label-software.md",
)
REQUIRED_README_LINKS = (
    "(https://github.com/grove/factory)",
    "(docs/README.md)",
    "(docs/reference/catalog.md)",
    "(docs/how-to/run-local.md)",
)


class DocumentationLinksTests(unittest.TestCase):
    def test_curated_local_links_and_anchors(self):
        """No external network or model dependency; review cross-repo links separately."""
        for name in PAGES:
            source = ROOT / name
            self.assertTrue(source.is_file(), f"Missing documentation page: {name}")
            for raw in LINK.findall(prose(source.read_text(encoding="utf-8"))):
                link = urlsplit(raw)
                if link.scheme or link.netloc:
                    continue
                with self.subTest(page=name, link=raw):
                    target = (source.parent / unquote(link.path)).resolve() if link.path else source
                    self.assertTrue(target.is_relative_to(ROOT), f"Link escapes repository: {raw}")
                    self.assertTrue(target.exists(), f"Missing local link: {raw}")
                    if link.fragment and target.is_file() and target.suffix == ".md":
                        self.assertIn(unquote(link.fragment), anchors(target.read_text(encoding="utf-8")))

    def test_product_entry_points_are_discoverable(self):
        for link in REQUIRED_README_LINKS:
            with self.subTest(link=link):
                self.assertIn(link, (ROOT / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
