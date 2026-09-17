"""Case-specific O-1B exhibit numbering and stable identities for saved drafts."""
import csv
import hashlib
import json
import re
from pathlib import Path

CRITERIA = ['lead_starring_productions', 'published_recognition', 'organization_role',
            'commercial_critical_success', 'significant_recognition', 'high_salary', 'comparable_evidence']


def exhibit_roles(loaded):
    """Return the present O-1B evidence groups in filing order.

    O-1B exhibit labels describe the order of the evidence actually included in
    the filing.  They must not inherit the statutory criterion numbers because
    an unclaimed criterion would then leave a gap (for example, 1, 3, 4, 6).
    """
    from .file_rules import is_prompt_sidecar, is_office_temporary_file
    from .workflow import folder_role_map

    claimed = loaded.config.get('claimed_criteria') or CRITERIA
    order = ['identity_cv_education', *claimed, 'recommendation_letters',
             'advisory_opinion', 'us_work_documents']
    roles = folder_role_map(loaded.config)
    result = {}
    for role in dict.fromkeys(order):
        if role == 'comparable_evidence' and loaded.config.get('o1b_track') == 'mptv':
            continue
        folder = roles.get(role)
        if not folder:
            continue
        present = any(
            p.is_file() and p.name != '.gitkeep' and not is_prompt_sidecar(p) and not is_office_temporary_file(p)
            for key in ('source_originals', 'source_translations', 'source_other')
            for p in (loaded.case_dir / loaded.config['paths'][key] / folder).rglob('*')
        )
        if present:
            result[role] = str(len(result) + 1)
    return result


def citation_plan(loaded, step, options):
    from .workflow import _repeatable_episode_candidates

    roles = step.get('evidence_folder_roles', [])
    role = roles[0] if len(roles) == 1 else ''
    if step.get('step_id') in {'o1b_petitioner_support_letter', 'o1b_itinerary', 'o1b_continuing_to_work'}:
        role = 'us_work_documents'
    number = exhibit_roles(loaded).get(role, '')
    if not number:
        return {}
    prefix = number + '.'
    if 'repeatable' in step.get('execution', ''):
        candidates = _repeatable_episode_candidates(loaded, step)
        folder = next((folder for eid, folder in candidates if eid == options.episode_id), '')
        if folder and folder != '.':
            position = next(i for i, (eid, _) in enumerate(candidates, 1) if eid == options.episode_id)
            prefix += f'{position}.'
    return {'exhibit_number': number, 'item_prefix': prefix}


def layout_plan(loaded):
    from .bundle_workflow import EvidenceLayoutPlan, _exhibit_metadata_for_output
    from .workflow import folder_role_map

    numbers = exhibit_roles(loaded)
    with (loaded.case_dir / loaded.config['paths']['document_index']).open(encoding='utf-8-sig') as handle:
        rows = list(csv.DictReader(handle))
    metadata = {}
    for role, number in numbers.items():
        step = next((s for s in loaded.workflow['steps'] if s.get('evidence_folder_roles') == [role]), {})
        title, _ = _exhibit_metadata_for_output(loaded, {'step_id': step.get('step_id', '')})
        if role == 'identity_cv_education':
            title = 'General documents: CV, education, and identity'
        elif role == 'us_work_documents':
            title = 'U.S. employment: offer, contracts, petitioner or agent documents, and itinerary'
        metadata[number] = (title or role.replace('_', ' ').title(), role)
    desired, order, episodes, titles = {}, {}, {}, {}
    folders = folder_role_map(loaded.config)
    for row in rows:
        role = row.get('category', '')
        if role not in numbers:
            continue
        doc_id = row['document_id']
        desired[doc_id] = numbers[role]
        order[doc_id] = len(order) + 1
        titles[doc_id] = row.get('display_title', '')
        # Folder identity, not an LLM-generated title, determines the episode.
        path = loaded.case_dir / row['file_path']
        for key in ('source_originals', 'source_translations', 'source_other'):
            try:
                parts = path.relative_to(loaded.case_dir / loaded.config['paths'][key] / folders[role]).parts
            except ValueError:
                continue
            episodes[doc_id] = parts[0] if len(parts) > 1 else ''
            break
    return EvidenceLayoutPlan(document_to_exhibit=desired, document_order=order,
        exhibit_order={number: i for i, number in enumerate(numbers.values(), 1)},
        document_titles=titles, document_episode_titles=episodes, conflicts=[],
        references=len(desired), exhibit_metadata=metadata)


def capture_draft_citations(loaded):
    """Record the old numbering before an index refresh; never modify draft prose."""
    from .bundle_workflow import _bundle_document_citation_index

    path = loaded.case_dir / 'indexes/o1b_draft_citations.json'
    saved = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    drafts = list((loaded.case_dir / 'draft_sections').rglob('*.md'))
    missing = [(p, hashlib.sha256(p.read_bytes()).hexdigest()) for p in drafts]
    missing = [(p, key) for p, key in missing if key not in saved]
    if not missing:
        return
    index = loaded.case_dir / loaded.config['paths']['exhibit_index']
    with index.open(encoding='utf-8-sig') as handle:
        roles = {r['exhibit_number']: r['memo_section'] for r in csv.DictReader(handle) if r.get('memo_section')}
    roles = roles or {number: role for role, number in exhibit_roles(loaded).items()}
    lookup = _bundle_document_citation_index(loaded)
    snapshot = {'roles': roles, 'documents': {number: doc_id for (_, number), doc_id in lookup['by_number'].items()}}
    for _, key in missing:
        saved[key] = snapshot
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8')


def render_draft_citations(loaded, draft_path, text):
    from .bundle_workflow import _bundle_document_citation_index, _normalize_citation_text

    snapshot_path = loaded.case_dir / 'indexes/o1b_draft_citations.json'
    if not snapshot_path.exists():
        return text
    snapshots = json.loads(snapshot_path.read_text(encoding='utf-8'))
    snapshot = snapshots.get(hashlib.sha256(draft_path.read_bytes()).hexdigest())
    if not snapshot:
        return text
    current = _bundle_document_citation_index(loaded)
    by_id = {doc_id: number for (_, number), doc_id in current['by_number'].items()}
    roles = exhibit_roles(loaded)

    def convert(number):
        if number in snapshot['documents'] and snapshot['documents'][number] in by_id:
            return by_id[snapshot['documents'][number]]
        top, *tail = number.split('.')
        new = roles.get(snapshot['roles'].get(top, ''), top)
        return '.'.join([new, *tail])

    # Resolve a citation by document title before old numeric labels: old LLM
    # labels may already disagree with the old index's episode grouping.
    def citation(match):
        value = match.group(0)
        normalized = _normalize_citation_text(value)
        matches = [(len(title), doc_id) for (_, title), ids in current['by_title'].items()
                   if len(title) > 8 and title in normalized for doc_id in ids]
        best = max((length for length, _ in matches), default=0)
        ids = {doc_id for length, doc_id in matches if length == best}
        if len(ids) == 1:
            number = by_id[next(iter(ids))]
            value = re.sub(r'(Exhibit\s+)\d+(?:\.\d+)*', lambda m: m[1] + number.split('.')[0], value, flags=re.I)
            value = re.sub(r'(PAGE\s*:\s*)\d+(?:\.\d+)+', lambda m: m[1] + number, value)
            return value
        return re.sub(r'(?<=Exhibit )\d+(?:\.\d+)*|(?<=PAGE: )\d+(?:\.\d+)+', lambda m: convert(m[0]), value)

    # Protect citations from the general exhibit replacement (no cascading).
    protected = []
    def protect(match):
        protected.append(citation(match))
        return f'@@O1BCITATION{len(protected)-1}@@'
    text = re.sub(r'\([^()]*\bExhibit\s+\d+[^()]*\)', protect, text)
    text = re.sub(r'\b(Exhibit\s+)(\d+(?:\.\d+)*)', lambda m: m[1] + convert(m[2]), text)
    def item(match):
        number, title = match[1], match[2]
        normalized = _normalize_citation_text(title)
        ids = {doc_id for (_, candidate), items in current['by_title'].items()
               if candidate == normalized for doc_id in items}
        return (by_id[next(iter(ids))] if len(ids) == 1 else convert(number)) + '. ' + title
    text = re.sub(r'^(\d+(?:\.\d+)+)\.\s+(.+)$', item, text, flags=re.M)
    for i, value in enumerate(protected):
        text = text.replace(f'@@O1BCITATION{i}@@', value)
    return text
