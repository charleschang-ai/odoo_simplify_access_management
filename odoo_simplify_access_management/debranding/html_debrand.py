# -*- coding: utf-8 -*-
"""移除邮件 HTML 中的 "Powered by Odoo" 品牌区块(公共实现)。

核心邮件模板(portal 邀请、auth_signup 重置密码、digest 等十几个模块)
的 body_html 里都内嵌同一结构的区块::

    <!-- POWERED BY -->
    <tr><td align="center" ...>
        <table ... background-color: #F1F1F1 ...>
          <tr><td>Powered by <a href="https://www.odoo.com?...">Odoo</a></td></tr>
        </table>
    </td></tr>

只删文字会留下一条空的灰色横带;用正则删整块又会在嵌套表格下误吞
正文。这里以 odoo.com 链接为锚点,用 lxml 逐层向上收拢到
"整个子树只含品牌短语"的最外层节点(即包住灰色表格的外层 <tr>),
整块删除。按文本内容而非固定文案匹配,因此对翻译后的正文同样生效
(如 zh_CN 的"由<a>Odoo</a>驱动")。lxml 解析失败时退回保守正则,
只删文字与链接,不动结构。
"""
import logging
import re

from lxml import etree, html as lxml_html

_logger = logging.getLogger(__name__)

# 品牌短语容器的可见文本上限:任何语言的 "Powered by Odoo" 短语都很短,
# 超过该长度说明该容器是正文内容,放弃整块删除。
_MAX_BLOCK_TEXT = 40

# 品牌链接的锚文本必须是 "Odoo" 或 "Odoo XXX"(如 Odoo CRM);
# 用户在正文里贴的裸网址链接(锚文本是 URL)不会命中,不受影响。
_BRAND_TEXT_RE = re.compile(r'^odoo(?:\s+[\w.-]+)?$', re.IGNORECASE)

# 保守回退(lxml 解析失败时用):仅移除品牌文字与链接,不动 HTML 结构。
# href 可能是静态 href,也可能是 qweb 动态属性 t-attf-href / t-att-href
# (如 auth_signup 的 "Settings: New Portal User Invite" 模板)。
_FALLBACK_RE = re.compile(
    r'(?:Powered\s+by\s*|由\s*)?'
    r'<a\b[^>]*(?:t-attf?-)?href="[^"]*odoo\.com[^"]*"[^>]*>\s*Odoo\s*</a>'
    r'(?:\s*驱动)?\.?',
    re.IGNORECASE)

_POWERED_COMMENT_RE = re.compile(r'powered\s*by', re.IGNORECASE)


def _norm_text(node):
    return ' '.join(node.text_content().split())


def _link_href(link):
    """链接目标:兼容静态 href 与 qweb 动态属性 t-attf-href / t-att-href。"""
    for attr in ('href', 't-attf-href', 't-att-href'):
        value = link.get(attr)
        if value:
            return value.lower()
    return ''


def _is_brand_link(link):
    return ('odoo.com' in _link_href(link)
            and bool(_BRAND_TEXT_RE.match(_norm_text(link))))


def _subtree_clean(container, link):
    """容器子树里除品牌链接外,不得有其他链接/图片/qweb 动态节点。"""
    for el in container.iter():
        if el is link or not isinstance(el.tag, str):
            continue  # 跳过链接本身与注释/PI 节点
        if el.tag in ('a', 'img'):
            return False  # 还有其他链接/图片,不能整块删
        if any(k.startswith('t-') for k in el.attrib):
            return False  # 含动态 qweb 节点,防误删业务内容
    return True


def _block_root(link, stop_node):
    """从品牌链接向上找可整块删除的最外层祖先。

    第一步:链接的直接父级必须是"短语容器" — 可见文本只是一个很短的
    品牌短语(如 "Powered by Odoo" / "由Odoo驱动"),且除链接外没有其他
    链接/图片/qweb 动态节点;否则说明链接嵌在正文里,返回链接本身。

    第二步:严格结构收拢 — 仅当父节点不引入任何新文本、且当前节点是
    父节点唯一的元素子节点时才继续向上(td → tr → 灰色 table → 外层
    td → 外层 tr),任何兄弟内容都会让收拢停在正确的层级。"""
    container = link.getparent()
    if container is None or container is stop_node:
        return link
    text = _norm_text(container)
    if len(text) > _MAX_BLOCK_TEXT or not _subtree_clean(container, link):
        return link
    best = container
    while True:
        parent = best.getparent()
        if parent is None or parent is stop_node or parent.tag in ('html', 'body'):
            break
        if _norm_text(parent) != text:
            break  # 父级引入了新的可见文本(兄弟节点有内容)
        if [c for c in parent if isinstance(c.tag, str)] != [best]:
            break  # 父级还有其他元素子节点
        best = parent
    return best


def _drop(node):
    """删除节点,但把尾随文本(tail)合并回文档,避免相邻文字丢失。"""
    parent = node.getparent()
    if parent is None:
        return
    tail = node.tail or ''
    if tail:
        prev = node.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or '') + tail
        else:
            parent.text = (parent.text or '') + tail
    parent.remove(node)


# 独立的 "Odoo" 品牌词(不匹配 odoo.com / odoo.sh 等域名片段)
_BRAND_WORD_RE = re.compile(r'\bodoo\b(?!\.(?:com|sh))', re.IGNORECASE)

# 品牌词替换跳过的元素:样式/脚本里的 odoo 多为类名或 URL
_SKIP_TAGS = {'style', 'script'}


def replace_odoo_text(text, brand):
    """纯文本(如邮件主题)中的独立 "Odoo" 品牌词替换为自有品牌名。"""
    if not text or not brand:
        return text
    return _BRAND_WORD_RE.sub(brand, text)


def replace_odoo_word(html_str, brand):
    """HTML 文本节点中的独立 "Odoo" 品牌词替换为自有品牌名。

    只处理元素的 text/tail 文本,不碰任何属性(href/src 里的域名安全),
    跳过 <style>/<script>。未命中或未配置品牌名时原样返回入参。"""
    if not html_str or not brand:
        return html_str
    source = str(html_str)
    if not _BRAND_WORD_RE.search(source):
        return html_str
    wrapper = html_str.__class__
    try:
        root = lxml_html.fragment_fromstring(source, create_parent='div')
    except (etree.ParserError, etree.XMLSyntaxError, ValueError):
        return html_str
    changed = False
    for el in root.iter():
        # tail 是元素之后的文本,属于父级内容,任何节点都要处理
        if el.tail and _BRAND_WORD_RE.search(el.tail):
            el.tail = _BRAND_WORD_RE.sub(brand, el.tail)
            changed = True
        if not isinstance(el.tag, str) or el.tag in _SKIP_TAGS:
            continue
        if el.text and _BRAND_WORD_RE.search(el.text):
            el.text = _BRAND_WORD_RE.sub(brand, el.text)
            changed = True
    if not changed:
        return html_str
    out = lxml_html.tostring(root, encoding='unicode', method='html')
    start = out.index('>') + 1
    end = out.rindex('<')
    return wrapper(out[start:end])


def remove_odoo_branding(html_str):
    """返回移除 "Powered by Odoo" 区块后的 HTML。

    未命中时原样返回入参(不重排原文);命中时返回与入参同类型
    (str/Markup)的清理结果。可安全重复调用(幂等)。
    """
    if not html_str:
        return html_str
    source = str(html_str)
    low = source.lower()
    if 'odoo.com' not in low and 'powered by' not in low:
        return html_str
    wrapper = html_str.__class__  # 与核心 _replace_local_links 一致,保持 Markup 类型
    try:
        root = lxml_html.fragment_fromstring(source, create_parent='div')
    except (etree.ParserError, etree.XMLSyntaxError, ValueError):
        return wrapper(_FALLBACK_RE.sub('', source))

    changed = False
    for link in list(root.iter('a')):
        if link.getparent() is None or not _is_brand_link(link):
            continue
        block = _block_root(link, root)
        if block is link:
            # 链接嵌在正文文字中(无独立包装容器),不动:
            # 只删除结构上独立的品牌区块,避免破坏用户自己的内容。
            continue
        # 相邻的 <!-- POWERED BY --> 注释一并移除
        prev = block.getprevious()
        if (prev is not None and prev.tag is etree.Comment
                and _POWERED_COMMENT_RE.search(prev.text or '')):
            _drop(prev)
        _drop(block)
        changed = True
    # 孤立残留的 POWERED BY 注释(如此前只删了文字的旧数据)
    for comment in list(root.iter(etree.Comment)):
        if _POWERED_COMMENT_RE.search(comment.text or ''):
            _drop(comment)
            changed = True
    if not changed:
        return html_str

    out = lxml_html.tostring(root, encoding='unicode', method='html')
    # 剥掉我们自己包上的 <div> 外壳
    start = out.index('>') + 1
    end = out.rindex('<')
    return wrapper(out[start:end])
