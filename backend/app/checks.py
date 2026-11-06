import re
from pypdf import PdfReader
from mutagen.mp4 import MP4


def duration(path):
    return float(MP4(path).info.length)


def numeral(text):
    if re.fullmatch(r'\d+(?:\.\d+)?', text):
        return float(text)
    digits = dict(zip('零一二三四五六七八九两', [0,1,2,3,4,5,6,7,8,9,2]))
    if text in digits:
        return digits[text]
    if '十' in text:
        left, right = text.split('十')
        if (not left or left in digits) and (not right or right in digits):
            return (digits.get(left, 1) * 10) + digits.get(right, 0)
    raise ValueError('无法解析数字')


def bounds(value, kind):
    text = re.sub(r'\s+', '', value)
    if kind == 'file_count':
        if not re.search(r'(?:份|个|张|项)?文件|截图|图片|份|张', text) or re.search('组|Prompt|迭代|链|内容', text, re.I):
            raise ValueError('未明确文件数量，请人工复核')
        text = re.sub(r'文件|截图|图片|份|张|个', '', text)
    elif kind == 'pdf_pages':
        if '页' not in text:
            raise ValueError('未明确页数单位，请人工复核')
        text = text.replace('PDF', '').replace('页', '')
    elif kind == 'video_duration':
        if '分' in text and '秒' in text:
            raise ValueError('混合时长单位未解析，请改为分钟范围或人工复核')
        unit = 60 if '分钟' in text or '分' in text else 1 if '秒' in text else None
        if unit is None:
            raise ValueError('未明确时长单位，请人工复核')
        text = text.replace('分钟', '').replace('分', '').replace('秒', '')
    number = r'(?:\d+(?:\.\d+)?|[零一二三四五六七八九十两]+)'
    ranged = re.fullmatch(f'({number})[-–—~～至到]({number})', text)
    if ranged:
        low, high = map(numeral, ranged.groups())
    else:
        matched = re.fullmatch(f'(不超过|最多|至多|≤|<=|至少|不低于|不少于|≥|>=|等于|恰好)?({number})(以内|以下|以上)?', text)
        if not matched:
            raise ValueError('无法解析约束，请编辑为明确范围或人工复核')
        op, number_text, suffix = matched.groups()
        n = numeral(number_text)
        if op in ('不超过','最多','至多','≤','<=') or suffix in ('以内','以下'):
            low, high = 0, n
        elif op in ('至少','不低于','不少于','≥','>=') or suffix == '以上':
            low, high = n, None
        else:
            low, high = n, n
    if high is not None and low > high:
        raise ValueError('范围下限大于上限，请修改要求')
    if kind == 'video_duration':
        low, high = low * unit, high * unit if high is not None else None
    return low, high


def time_text(seconds):
    return f'{seconds:.2f} 秒（{int(seconds)//60:02d}:{int(seconds)%60:02d}）'


def run_checks(item, files, path_for, now):
    results = []
    def result(kind, actual, expected, status, quote='', source='', reason=''):
        results.append(dict(type=kind, actual=str(actual), expected=expected, status=status,
                            quote=quote, source_ref=source, reason=reason, checked_at=now))
    present = [f for f in files if path_for(f).is_file()]
    if item.get('required', True):
        result('exists', f'{len(present)} / {len(files)} 个文件存在', '已选定文件存在且非空集合',
               'pass' if files and len(present) == len(files) else 'fail', item.get('quote',''), item.get('source_ref',''))
    elif not files:
        result('exists','未选定','建议项','pending',reason='建议项未提交')
        return results
    for constraint in item.get('constraints', []):
        kind, value = constraint['type'], constraint['value']
        quote, source = constraint.get('quote',''), constraint.get('source_ref') or item.get('source_ref','')
        if kind == 'content':
            result(kind,'未自动判断',value,'pending',quote,source,'请人工复核')
            continue
        try:
            if kind == 'extension':
                allowed = re.findall(r'(?i)(?:PDF|MP4|DOCX|DOC|TXT|MD|PNG|JPG|JPEG|ZIP|PY|JS|TS)(?![A-Za-z0-9])', value)
                remainder = re.sub(r'(?i)(?:PDF|MP4|DOCX|DOC|TXT|MD|PNG|JPG|JPEG|ZIP|PY|JS|TS)(?![A-Za-z0-9])|格式|文件|或|、|/|\.|，|,|\s', '', value)
                if not allowed or remainder:
                    raise ValueError('无法解析格式约束，请编辑要求或人工复核')
                actual = ', '.join(f['original_name'] + ': ' + f['extension'] for f in files) or '未选定文件'
                result(kind,actual,value,'pass' if files and all(f['extension'].lstrip('.').upper() in [x.upper() for x in allowed] for f in files) else 'fail',quote,source)
                continue
            if kind == 'file_count' and (not re.search(r'文件|份|张|截图|图片', quote) or re.search('组|Prompt|迭代|链|内容', quote, re.I)):
                raise ValueError('原文未明确文件数量，请人工复核')
            parsed_value = value + '个文件' if kind == 'file_count' and re.fullmatch(r'\d+', value) else value
            low, high = bounds(parsed_value, kind)
            if kind == 'file_count':
                actuals = [len({f['id'] for f in files})]
                actual = f'{actuals[0]} 个文件'
            elif kind == 'pdf_pages':
                if not files:
                    result(kind,'未选定文件',value,'pending',quote,source,'请选定 PDF 后重新检查');continue
                if any(f['extension'] != '.pdf' for f in files):
                    raise ValueError('选定文件不是 PDF，请重新选择')
                actuals = [len(PdfReader(path_for(f)).pages) for f in files]
                actual = '；'.join(f"{f['original_name']}：{n} 页" for f,n in zip(files,actuals))
            elif kind == 'video_duration':
                if not files:
                    result(kind,'未选定文件',value,'pending',quote,source,'请选定 MP4 后重新检查');continue
                if any(f['extension'] != '.mp4' for f in files):
                    raise ValueError('选定文件不是 MP4，请重新选择')
                actuals = [duration(path_for(f)) for f in files]
                actual = '；'.join(f"{f['original_name']}：{time_text(n)}" for f,n in zip(files,actuals))
            else:
                raise ValueError('无法自动判断，请人工复核')
            status = 'pass' if all(n >= low and (high is None or n <= high) for n in actuals) else 'fail'
            result(kind,actual,value,status,quote,source)
        except ValueError as error:
            result(kind,'未判断',value,'pending',quote,source,str(error))
        except Exception as error:
            label = 'PDF 页数' if kind == 'pdf_pages' else 'MP4 时长'
            result(kind,'读取异常',value,'error',quote,source,f'无法读取{label}（{type(error).__name__}），请更换文件后重新检查')
    return results


def status(item):
    if not item.get('confirmed') or item.get('stale'):
        return 'excluded'
    checks = item.get('last_check_result')
    if checks is None:
        return 'unchecked'
    review = item.get('review_decision', 'pending')
    if any(c['status'] == 'fail' for c in checks) or review == 'fail':
        return 'fail'
    if any(c['status'] == 'error' for c in checks):
        return 'pending'
    needs_review = item.get('needs_manual_review') or any(c['status']=='pending' for c in checks)
    if needs_review and review != 'pass':
        return 'pending'
    return 'pass'
