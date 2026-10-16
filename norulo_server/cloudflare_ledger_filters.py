"""Disjoint grant filters with room for owner, cursor and optional predicates."""
PROJECT_FILTER_CHUNK = 50


def project_filters(project_ids, *, column="project_id"):
    """Return disjoint SQL filters over an already validated project grant.

    No grant restriction is one unrestricted query; an empty grant is no query.
    Column names are application constants, never HTTP input.
    """
    if column not in {"id", "project_id"}:
        raise ValueError("project filter column")
    if project_ids is None:
        return [("", [])]
    return [(" AND " + column + " IN (" + ",".join("?" for _ in group) + ")", group)
            for start in range(0, len(project_ids), PROJECT_FILTER_CHUNK)
            for group in [project_ids[start:start + PROJECT_FILTER_CHUNK]]]


def restriction_filters(restrictions):
    """Include the shared pool exactly once when combining project chunks."""
    project_ids = restrictions.get("projectIds")
    shared = restrictions.get("shared") is True
    if project_ids is None:
        return [("", [])] if shared else [(" AND target_kind='project'", [])]
    filters = project_filters(project_ids)
    if shared:
        if not filters:
            return [(" AND target_kind='shared'", [])]
        clause, values = filters[0]
        filters[0] = (" AND (" + clause.removeprefix(" AND ") + " OR target_kind='shared')", values)
    return filters


def merge_page(parts, limit, *, columns=("id",)):
    """Merge disjoint sorted prefixes before applying the global page limit."""
    return sorted((row for part in parts for row in part.results),
                  key=lambda row: tuple(row[column] for column in columns))[:limit]
