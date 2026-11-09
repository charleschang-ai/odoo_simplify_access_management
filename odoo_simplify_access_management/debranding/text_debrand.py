# -*- coding: utf-8 -*-
"""界面文字中的 "Odoo" 品牌词替换(服务端公共实现)。

用于后台视图结构(arch)、字段标签/帮助/选项、QWeb 模板的静态文字。
只替换独立、首字母大写的 "Odoo" 单词:

- 不碰 odoo.com / odoo.sh 等域名、"OdooBot" 等组合词、小写的技术标识;
- 只处理文本节点与"展示用"属性(string/help/placeholder/title 等),
  不碰 name/class/domain/href 等逻辑属性;
- QWeb 表达式里只替换形如 'Odoo' / 'Odoo Report' 的兜底字符串字面量
  (如 <title t-out="title or 'Odoo'"/>),不改其他表达式。
"""
import re

# re.ASCII:中文字符在 Unicode 模式下算单词字符,"您的Odoo帐户" 会匹配不到
ODOO_WORD_RE = re.compile(r'\bOdoo\b(?!\.(?:com|sh)\b)', re.ASCII)

# 展示用属性(视图与模板通用)
TEXT_ATTRS = frozenset({
    'string', 'help', 'placeholder', 'title', 'confirm', 'alt', 'aria-label',
    'data-tooltip', 'sum', 'avg', 'label', 'data-oe-demo',
})
# 其内容不是给人看的文字
SKIP_TEXT_TAGS = frozenset({'script', 'style', 'code', 'pre'})
# 直接输出到页面的 QWeb 表达式属性
OUTPUT_EXPR_ATTRS = frozenset({'t-out', 't-esc', 't-raw'})
# QWeb 表达式中的兜底字符串字面量:'Odoo'、"Odoo Report" 等
EXPR_LITERAL_RE = re.compile(r"""(['"])Odoo((?: [A-Za-z]+)*)\1""")


def has_odoo(text):
    return bool(text) and 'Odoo' in text and bool(ODOO_WORD_RE.search(text))


def replace_text(text, brand):
    """纯文本中的 "Odoo" 品牌词替换为品牌名;未命中原样返回。"""
    if not brand or not has_odoo(text):
        return text
    return ODOO_WORD_RE.sub(lambda _m: brand, text)


def _replace_literals(expr, brand):
    def sub(match):
        quote = match.group(1)
        safe = brand.replace('\\', '\\\\').replace(quote, '\\' + quote)
        return '%s%s%s%s' % (quote, safe, match.group(2), quote)
    return EXPR_LITERAL_RE.sub(sub, expr)


def debrand_tree(root, brand, qweb=False):
    """原地替换 etree 中的品牌词,返回是否有修改。

    :param qweb: QWeb 模板模式:额外处理 <meta content>(如 website 的
        generator、登录页的 og:site_name)与表达式里的兜底字面量。
    """
    if not brand:
        return False
    changed = False
    to_remove = []
    for el in root.iter():
        tail = el.tail
        if tail and has_odoo(tail):
            el.tail = replace_text(tail, brand)
            changed = True
        tag = el.tag
        if not isinstance(tag, str):
            continue  # 注释 / 处理指令
        if el.text and tag not in SKIP_TEXT_TAGS and has_odoo(el.text):
            el.text = replace_text(el.text, brand)
            changed = True
        for attr, value in el.attrib.items():
            if not value or 'Odoo' not in value:
                continue
            if attr in TEXT_ATTRS:
                new = replace_text(value, brand)
            elif qweb and tag == 'meta' and attr == 'content':
                if value.strip() == '@Odoo':  # twitter:site 指向 Odoo 官方账号
                    to_remove.append(el)
                    changed = True
                    continue
                new = replace_text(value, brand)
            elif qweb and (attr in OUTPUT_EXPR_ATTRS or (
                    attr.startswith('t-att-') and attr[6:] in TEXT_ATTRS | {'content'})):
                # 只改直接输出到页面的表达式;t-if / t-value 等可能拿字面量
                # 做比较或当作标识,不动
                new = _replace_literals(value, brand)
            else:
                continue
            if new != value:
                el.set(attr, new)
                changed = True
    for el in to_remove:
        parent = el.getparent()
        if parent is not None:
            if el.tail:
                prev = el.getprevious()
                if prev is not None:
                    prev.tail = (prev.tail or '') + el.tail
                else:
                    parent.text = (parent.text or '') + el.tail
            parent.remove(el)
    return changed


def get_brand(env):
    """白标启用时返回品牌名(未填则用公司名),否则返回空串。

    注册表未就绪(模块安装/升级过程中)时不处理:此时 sam.profile 的表
    可能尚未建立,且视图校验等过程不需要白标。"""
    if not env.registry.ready or 'sam.profile' not in env:
        return ''
    profile_model = env['sam.profile'].sudo()
    if not profile_model._get_debranding().get('enabled'):
        return ''
    return profile_model._sam_bot_branding()[0]
