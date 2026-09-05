def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def pct_change(a, b):
    """a 相对 b 的百分比变化；(a-b)/b。b=0 时返回 None。"""
    if b == 0:
        return None
    return (a - b) / b
