import re

LABELS = {'pass':'通过','fail':'不通过','pending':'待复核','unchecked':'待检查','excluded':'待处理','error':'检查异常'}


def archive_path(item):
    name = item['original_name'].replace('\\','/').rsplit('/',1)[-1]
    name = re.sub(r'[\x00-\x1f\x7f]', '_', name)
    if name in ('', '.', '..'):
        name = '未命名文件'
    return f"materials/{item['id']}/{name}"


def report(project, summary, packed, selected, generated):
    lines = [f"# {project['name']}：验收报告", '', f'生成时间：{generated}',
             f"任务来源：{project['task_source']} / {project.get('task_filename') or '粘贴文本'}",
             f"当前必交验收状态：{LABELS[summary['overall']]}", '', '## 实际打包文件', '']
    packed_ids = {f['id'] for f in packed}
    if not packed:
        lines.append('材料为空，本次 ZIP 仅包含验收报告。')
    for f in packed:
        lines.append(f"- {archive_path(f)}（{f['bytes']} 字节）")
    unresolved = []
    for item in summary['items']:
        pending = item['status'] == 'excluded' or bool(item.get('source_issues'))
        state = '待处理' if pending else LABELS[item['status']]
        lines += ['', f"## {item['title']}", f"类别：{'必交' if item['required'] else '建议'}；状态：{state}",
                  item['description'], f"原文出处：{item.get('source_ref') or '待定位'}", item.get('quote',''), '', '### 验收选定文件']
        evidence = selected.get(item['id'], [])
        lines.extend([f"- {f['original_name']}（{f['id']}）" for f in evidence] or ['未选定成果。'])
        omitted = [f for f in evidence if f['id'] not in packed_ids]
        if omitted:
            warning = '验收关联证据未包含在本次 ZIP：' + '、'.join(f['original_name'] for f in omitted)
            lines.append(warning)
            unresolved.append(item['title'] + '：' + warning)
        if state != '通过':
            unresolved.append(item['title'] + '：' + state)
        if pending:
            lines.append('待处理：' + ('原文已变' if item.get('stale') else '出处有歧义' if item.get('source_issues') else '未确认'))
            for issue in item.get('source_issues', []):
                lines += [issue['reason'], issue['quote']]
            continue
        lines += ['', '### 系统检查']
        for check in item.get('last_check_result') or []:
            lines += [f"- {check['type']}：{LABELS[check['status']]}", f"  实际：{check['actual']}",
                      f"  要求：{check['expected']}", f"  依据：{check['source_ref']} / {check['quote']}",
                      f"  检查时间：{check['checked_at']}", f"  说明：{check['reason']}"]
        if not item.get('last_check_result'):
            lines.append('尚未检查。')
        decision = {'pass':'人工确认符合','fail':'人工确认不符合','pending':'未复核'}[item.get('review_decision','pending')]
        lines += ['', '### 人工复核', decision, item.get('review_note',''), f"复核时间：{item.get('reviewed_at') or '未复核'}"]
    lines += ['', '## 未解决项', ''] + (['- '+x for x in unresolved] or ['无已记录的未解决项。'])
    return '\n'.join(lines) + '\n'
