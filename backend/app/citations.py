import re


def contexts(segments):
    stack=[]
    result={}
    for segment in segments:
        heading=re.match(r'^(#{1,6})\s+(.+)',segment['text'])
        if heading:
            level=len(heading[1])
            stack=[h for h in stack if h[0]<level]+[(level,heading[2].strip(),segment['ref'])]
        result[segment['ref']]=tuple(stack)
    return result


def locate_quote(quote, segments, candidate='', parent=''):
    matches=[s for s in segments if quote and quote in s['text']]
    ctx=contexts(segments)
    by_ref={s['ref']:s for s in segments}
    scopes=[]
    if candidate in by_ref:
        # An exact content fragment is stronger than a section hint.
        if quote in by_ref[candidate]['text']:
            matches=[by_ref[candidate]]
        else:
            matches=[s for s in matches if ctx[s['ref']]==ctx[candidate]] if by_ref[candidate]['text'].startswith('#') else []
    else:
        ranges=re.findall(r'行\s*(\d+)(?:\s*[-–—]\s*(\d+))?\s*/\s*([^；;]+)',candidate)
        if ranges:
            for s in matches:
                line=re.match(r'行 (\d+)',s['ref'])
                if line and any(int(lo)<=int(line[1])<=int(hi or lo) and s['ref'].split(' / ',1)[-1]==title.strip() for lo,hi,title in ranges):scopes.append(s)
            matches=scopes
        elif candidate:
            scoped=[s for s in matches if any(candidate==h[1] for h in ctx[s['ref']])]
            if any(candidate==h[1] for values in ctx.values() for h in values):matches=scoped
    if len(matches)>1 and parent in ctx and ctx[parent]:
        root=ctx[parent][0]
        matches=[s for s in matches if ctx[s['ref']] and ctx[s['ref']][0]==root]
    if len(matches)==1:
        if parent in ctx and ctx[parent] and ctx[matches[0]['ref']] and ctx[parent][0]!=ctx[matches[0]['ref']][0]:
            raise ValueError('引文属于其他章节，请核对当前要求')
        return matches[0]['ref']
    if not matches:raise ValueError('引文与候选章节不匹配或原文未找到，请核对引文')
    raise ValueError('引文匹配多处，请选择章节与来源片段')


def resolve_draft(item, segments):
    data=item.model_dump()
    issues=[]
    ctx=contexts(segments)
    def resolve(target,path,parent=''):
        candidate=target.get('source_ref','')
        try:target['source_ref']=locate_quote(target['quote'],segments,candidate,parent)
        except ValueError as error:
            target['source_ref']=''
            issues.append({'field':path,'reason':str(error),'candidate':candidate,'quote':target['quote'],
                           'matches':[{'ref':s['ref'],'section':' / '.join(h[1] for h in ctx[s['ref']])} for s in segments if target['quote'] and target['quote'] in s['text']]})
    resolve(data,'source_ref')
    for i,constraint in enumerate(data['constraints']):resolve(constraint,f'constraints.{i}.source_ref',data['source_ref'])
    data['source_issues']=issues
    return data


def resolve_sources(items, segments):
    for item in items:
        data=resolve_draft(item,segments)
        if data['source_issues']:raise ValueError(data['source_issues'][0]['reason'])
        item.source_ref=data['source_ref']
        for target,source in zip(item.constraints,data['constraints']):target.source_ref=source['source_ref']
    return items
