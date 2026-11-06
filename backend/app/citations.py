def locate_quote(quote, segments):
    matches = [s['ref'] for s in segments if quote and quote in s['text']]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f'引文未找到：{quote}。请核对原文后手动添加')
    raise ValueError(f'引文匹配多处：{quote}（{"、".join(matches)}）。请补充可区分的原文')


def resolve_sources(items, segments):
    for item in items:
        item.source_ref = locate_quote(item.quote, segments)
        for constraint in item.constraints:
            constraint.source_ref = locate_quote(constraint.quote, segments)
    return items
