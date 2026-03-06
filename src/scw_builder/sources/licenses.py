from __future__ import annotations

import html
import re
from typing import Any

from scw_builder.manifest import Attribution


def attribution_lines(attribution: Attribution) -> list[str]:
    lines = [f"- **Title:** {attribution.title}"]
    if attribution.author:
        lines.append(f"- **Author:** {attribution.author}")
    if attribution.creator and attribution.creator != attribution.author:
        lines.append(f"- **Creator:** {attribution.creator}")
    if attribution.date:
        lines.append(f"- **Date:** {attribution.date}")
    if attribution.identifier:
        lines.append(f"- **Identifier:** {attribution.identifier}")
    if attribution.license_name:
        license_line = f"- **License:** {attribution.license_name}"
        if attribution.license_url:
            license_line += f" ({attribution.license_url})"
        lines.append(license_line)
    if attribution.rights_statement:
        lines.append(f"- **Rights:** {attribution.rights_statement}")
    if attribution.source_url:
        lines.append(f"- **Source:** {attribution.source_url}")
    if attribution.attribution_text:
        lines.append(f"- **Required Attribution:** {attribution.attribution_text}")
    if attribution.attribution_html:
        lines.append(f"- **Attribution HTML:** `{attribution.attribution_html}`")
    return lines


def normalize_commons_attribution(
    title: str,
    metadata: dict[str, Any],
    source_url: str,
) -> Attribution:
    imageinfo = _first_imageinfo(metadata)
    extmetadata = imageinfo.get("extmetadata", {})
    artist = _clean_extmetadata_value(extmetadata, "Artist")
    credit = _clean_extmetadata_value(extmetadata, "Credit")
    license_name = _clean_extmetadata_value(extmetadata, "LicenseShortName")
    license_url = _clean_extmetadata_value(extmetadata, "LicenseUrl")
    attribution_text = _clean_extmetadata_value(extmetadata, "Attribution")
    attribution_html = _extmetadata_value(extmetadata, "Attribution")

    author = artist or credit
    return Attribution(
        title=_clean_extmetadata_value(extmetadata, "ObjectName") or title,
        author=author,
        creator=author,
        license_name=license_name,
        license_url=license_url,
        source_url=source_url,
        attribution_text=attribution_text or credit,
        attribution_html=attribution_html if attribution_html != attribution_text else None,
    )


def normalize_ia_attribution(identifier: str, metadata: dict[str, Any]) -> Attribution:
    title = _stringify_ia_field(metadata, "title") or identifier
    creator = _stringify_ia_field(metadata, "creator")
    date = _stringify_ia_field(metadata, "date")
    rights = _stringify_ia_field(metadata, "rights")
    license_url = _stringify_ia_field(metadata, "licenseurl")
    source_url = f"https://archive.org/details/{identifier}"
    attribution_text = rights or license_url
    return Attribution(
        title=title,
        author=creator,
        creator=creator,
        date=date,
        identifier=identifier,
        license_name=rights or "See rights statement",
        license_url=license_url,
        rights_statement=rights,
        source_url=source_url,
        attribution_text=attribution_text,
    )


def commons_has_required_attribution(metadata: dict[str, Any]) -> bool:
    imageinfo = _first_imageinfo(metadata)
    extmetadata = imageinfo.get("extmetadata", {})
    author = _clean_extmetadata_value(extmetadata, "Artist") or _clean_extmetadata_value(
        extmetadata, "Credit"
    )
    license_name = _clean_extmetadata_value(extmetadata, "LicenseShortName")
    license_url = _clean_extmetadata_value(extmetadata, "LicenseUrl")
    source_url = imageinfo.get("descriptionurl") or imageinfo.get("url")
    return bool(author and license_name and license_url and source_url)


def ia_has_usable_rights(metadata: dict[str, Any]) -> bool:
    rights = (_stringify_ia_field(metadata, "rights") or "").lower()
    license_url = (_stringify_ia_field(metadata, "licenseurl") or "").lower()
    safe_markers = [
        "public domain",
        "no known copyright restrictions",
        "creativecommons.org/publicdomain",
        "creativecommons.org/licenses",
    ]
    return any(marker in rights or marker in license_url for marker in safe_markers)


def _first_imageinfo(metadata: dict[str, Any]) -> dict[str, Any]:
    pages = metadata.get("query", {}).get("pages", {})
    if not pages:
        return {}
    first_page = next(iter(pages.values()))
    imageinfo = first_page.get("imageinfo", [])
    return imageinfo[0] if imageinfo else {}


def _extmetadata_value(extmetadata: dict[str, Any], key: str) -> str | None:
    raw = extmetadata.get(key)
    if not raw:
        return None
    value = raw.get("value")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _clean_extmetadata_value(extmetadata: dict[str, Any], key: str) -> str | None:
    value = _extmetadata_value(extmetadata, key)
    if not value:
        return None
    no_tags = re.sub(r"<[^>]+>", " ", value)
    normalized = re.sub(r"\s+", " ", html.unescape(no_tags)).strip()
    return normalized or None


def _stringify_ia_field(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get("metadata", {}).get(key)
    if isinstance(value, list):
        joined = ", ".join(str(item).strip() for item in value if str(item).strip())
        return joined or None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None
