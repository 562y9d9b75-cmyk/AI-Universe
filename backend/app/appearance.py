"""Curated fictional portraits and validated visual character configuration.

Appearance is presentation metadata only: it never grants skills or permissions.
The allowlist deliberately excludes remote URLs and arbitrary local file paths.
"""
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CharacterProfileInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    nationality: Literal['CN', 'GB', 'FR'] = 'CN'
    age_range: Literal['20-29', '30-39', '40-49', '50-59', '60+'] = '30-39'
    presentation: Literal['masculine', 'feminine', 'androgynous'] = 'masculine'
    description: str = Field(default='', max_length=1000)


class AppearanceInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    portrait_id: str = Field(default='lin-yuan', min_length=1, max_length=80)
    avatar_url: str = Field(default='', min_length=1, max_length=200)
    character_profile: CharacterProfileInput = Field(default_factory=CharacterProfileInput)
    # Backwards-compatible placement hint for the original eight employees.
    index: int = Field(default=0, ge=0, le=7)


# Stable IDs identify visual assets, independently of editable employee names.
_CHARACTERS = [
    ('lin-yuan', '林远', 'Atlas', 'AI CEO', '战略与运营', 'CN', '40-49', 'masculine', '沉稳干练，深色西装与自然短发'),
    ('shen-zhixia', '沈知夏', 'Emma', '市场研究员', '市场与数据', 'CN', '20-29', 'feminine', '自然中长发，浅色职业装'),
    ('zhou-yuan', '周予安', 'Alex', '数据分析师', '市场与数据', 'CN', '30-39', 'masculine', '清爽短发，衬衫与休闲西装'),
    ('su-yining', '苏以宁', 'Sophia', '产品经理', '产品与技术', 'CN', '30-39', 'feminine', '利落发型，简洁有质感的职业装'),
    ('chen-yan', '陈砚', 'Mike', '技术工程师', '产品与技术', 'CN', '30-39', 'masculine', '短发，舒适的针织与衬衫'),
    ('xu-xinglan', '许星澜', 'Lily', '创意总监', '创意与内容', 'CN', '30-39', 'feminine', '利落短发，具有设计感的日常着装'),
    ('gu-mingchuan', '顾明川', 'David', '财务分析师', '财务与管理', 'CN', '40-49', 'masculine', '成熟稳重，精致衬衫与西装'),
    ('lu-jingxing', '陆景行', 'Noah', '项目经理', '战略与运营', 'CN', '30-39', 'masculine', '亲和利落，商务休闲着装'),
    ('olivia-morgan', 'Olivia Morgan', None, None, None, 'GB', '30-39', 'feminine', '英国虚拟人物，33岁，自然职业着装'),
    ('lucas-martin', 'Lucas Martin', None, None, None, 'FR', '30-39', 'masculine', '法国虚拟人物，38岁，自然职业着装'),
]

PORTRAITS = {
    row[0]: {
        'id': row[0],
        'name': row[1],
        'avatar_url': '/assets/portraits/' + row[0] + '.png',
        'available': True,
        'character_profile': {
            'nationality': row[5], 'age_range': row[6],
            'presentation': row[7], 'description': row[8],
        },
    }
    for row in _CHARACTERS
}
DEFAULT_EMPLOYEES = [
    {'portrait_id': r[0], 'name': r[1], 'legacy_name': r[2], 'role': r[3], 'department': r[4]}
    for r in _CHARACTERS[:8]
]


def appearance_catalog():
    return {
        'portraits': deepcopy(list(PORTRAITS.values())),
        'nationalities': [{'value': 'CN', 'label': '中国'}, {'value': 'GB', 'label': '英国'}, {'value': 'FR', 'label': '法国'}],
        'age_ranges': ['20-29', '30-39', '40-49', '50-59', '60+'],
        'presentations': [{'value': 'masculine', 'label': '男性形象'}, {'value': 'feminine', 'label': '女性形象'}, {'value': 'androgynous', 'label': '中性形象'}],
        'default_portrait_id': 'lin-yuan',
    }


def default_appearance(portrait_id='lin-yuan', index=None):
    portrait = PORTRAITS[portrait_id]
    result = {k: deepcopy(portrait[k]) for k in ['avatar_url', 'character_profile']}
    result['portrait_id'] = portrait_id
    if index is not None:
        result['index'] = index
    return result


def normalize_appearance(value, current=None, default_id='lin-yuan'):
    """Validate a partial appearance update and return a complete safe record."""
    model = AppearanceInput.model_validate(value)
    patch = model.model_dump(exclude_unset=True)
    if not patch:
        raise ValueError('形象配置不能为空')
    current = current if isinstance(current, dict) else {}
    portrait_id = patch.get('portrait_id')
    if 'avatar_url' in patch:
        by_url = next((p['id'] for p in PORTRAITS.values() if p['avatar_url'] == patch['avatar_url']), None)
        if not by_url or (portrait_id and by_url != portrait_id):
            raise ValueError('头像必须与所选本地人物模板一致')
        portrait_id = by_url
    portrait_id = portrait_id or current.get('portrait_id', default_id)
    if portrait_id not in PORTRAITS:
        raise ValueError('请选择已交付的人物形象')
    result = default_appearance(portrait_id)
    if current.get('portrait_id') == portrait_id and isinstance(current.get('character_profile'), dict):
        # Revalidate persisted profiles rather than trusting arbitrary old JSON.
        try:
            result['character_profile'] = CharacterProfileInput.model_validate(current['character_profile']).model_dump()
        except ValueError:
            pass
    result['character_profile'].update(patch.get('character_profile', {}))
    if result['character_profile']['nationality'] != PORTRAITS[portrait_id]['character_profile']['nationality']:
        raise ValueError('人物地区必须与所选头像模板一致，请选择对应地区的人物')
    if 'index' in patch:
        result['index'] = patch['index']
    elif type(current.get('index')) is int and 0 <= current['index'] <= 7:
        result['index'] = current['index']
    return result
