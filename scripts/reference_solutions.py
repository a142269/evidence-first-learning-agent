"""
reference_solutions.py — 8 道 D2 编程题 sandbox 兼容参考实现 (Round 6 R2 + Round 7)

所有实现遵守 sandbox 约束:
- 无 import / 无下标 obj[i] / 无解包 a, b = expr
- 关键技巧: list.pop(0) 拆 pair, sorted 默认按首元素, dict.get(k)
- 避免: from __future__ import (含 __future__ 触发 transform 命名限制)

Round 7 新增: MLP 用 pop 链矩阵操作库 + 真 sigmoid/反向算法
"""



# ============================================================
# 1. KNN
# ============================================================
REFERENCE_KNN = '''
def knn_classify(X_train, y_train, x_test, k=3):
    dists = []
    xt = []
    yt = []
    for v in X_train:
        xt.append(v)
    for v in y_train:
        yt.append(v)
    while len(xt) > 0:
        row = xt.pop(0)
        label = yt.pop(0)
        aa = []
        bb = []
        for v in row:
            aa.append(v)
        for v in x_test:
            bb.append(v)
        s = 0.0
        while len(aa) > 0:
            x = aa.pop(0)
            y = bb.pop(0)
            d = x - y
            s = s + d * d
        dists.append([s ** 0.5, label])
    dists = sorted(dists)
    topk = []
    for i in range(k):
        topk.append(dists.pop(0))
    counts = {}
    for p in topk:
        d = p.pop(0)
        l = p.pop(0)
        if l in counts:
            counts[l] = counts.get(l) + 1
        else:
            counts[l] = 1
    best_label = None
    best_count = -1
    for key in counts:
        c = counts.get(key)
        if c > best_count:
            best_count = c
            best_label = key
    return best_label
'''


# ============================================================
# 2. Linear Regression GD
# ============================================================
REFERENCE_LINREG = '''
def linear_regression_gd(X, y, lr=0.01, epochs=1000):
    w = 0.0
    b = 0.0
    n = 0
    for v in X:
        n = n + 1
    for epoch in range(epochs):
        gw = 0.0
        gb = 0.0
        xi = []
        for v in X:
            xi.append(v)
        yi = []
        for v in y:
            yi.append(v)
        for i in range(n):
            x = xi.pop(0)
            yt = yi.pop(0)
            pred = w * x + b
            err = pred - yt
            gw = gw + err * x
            gb = gb + err
        gw = gw / n
        gb = gb / n
        w = w - lr * gw
        b = b - lr * gb
    return [w, b]  # 改: 返回 list, 让 harness 用 pop 拆
'''


# ============================================================
# 3. ID3 Information Gain (带索引转换)
# split_indices: 索引分组 (e.g. [[0,1],[2,3]] 表示 split 后各分支取原 labels 的哪些 index)
# 实际转: 各分支的 labels = [labels[i] for i in group]
# ============================================================
REFERENCE_ID3 = '''
def calc_info_gain(labels, split_indices):
    n = 0
    for v in labels:
        n = n + 1
    # 复制 labels
    labels_copy = []
    for v in labels:
        labels_copy.append(v)
    def entropy(label_list, total):
        if total == 0:
            return 0.0
        counts = {}
        for l in label_list:
            if l in counts:
                counts[l] = counts.get(l) + 1
            else:
                counts[l] = 1
        h = 0.0
        for key in counts:
            p = counts.get(key) / total
            if p > 0 and p < 1:
                # ln(p) = ln(1+x) series, x = p-1, |x| < 1
                # ln(1+x) = x - x²/2 + x³/3 - x⁴/4 + ... (alternating)
                sign = 1
                k = 1
                term = p - 1.0
                s = 0.0
                while k < 200:
                    s = s + sign * term / k
                    sign = -sign
                    term = term * (p - 1.0)
                    k = k + 1
                ln_p = s
                h = h - p * (ln_p / 0.693147)
        return h
    # 索引 -> labels 转换 (每次外层 idx 重新复制 labels)
    def indices_to_labels(group, lbls):
        out = []
        gc = []
        for v in group:
            gc.append(v)
        while len(gc) > 0:
            idx = gc.pop(0)
            # 每次重新复制 labels, 跳过 idx 个, 拿第 idx 个
            lc = []
            for v in lbls:
                lc.append(v)
            target = None
            i = 0
            while i <= idx:
                if len(lc) > 0:
                    target = lc.pop(0)
                i = i + 1
            if target is not None:
                out.append(target)
        return out
    h_total = entropy(labels, n)
    h_split = 0.0
    for group in split_indices:
        g_labels = indices_to_labels(group, labels)
        g_n = 0
        for v in g_labels:
            g_n = g_n + 1
        if g_n == 0:
            continue
        h_split = h_split + (g_n / n) * entropy(g_labels, g_n)
    return h_total - h_split
'''


# ============================================================
# 4. MLP Forward-Backward — Round 7 真实现
# 2 -> 3 -> 1, sigmoid + BCE 反向
# 全 pop 链, sandbox 兼容
# ============================================================
REFERENCE_MLP = '''
def mlp_forward_backward(X, y, W1, b1, W2, b2):
    # ---- helper: 通用 list/matrix 操作 (pop 链, sandbox 兼容) ----
    def cp(L):
        out = []
        for v in L:
            out.append(v)
        return out
    def row_at(M, idx):
        c = cp(M)
        r = None
        for _ in range(idx + 1):
            r = c.pop(0)
        return r
    def get_at(M, i, j):
        r = row_at(M, i)
        rc = cp(r)
        v = None
        for _ in range(j + 1):
            v = rc.pop(0)
        return v
    def replace_at(L, idx, val):
        out = []
        c = cp(L)
        i = 0
        while len(c) > 0:
            old = c.pop(0)
            if i == idx:
                out.append(val)
            else:
                out.append(old)
            i = i + 1
        return out
    def zeros_mat(rows, cols):
        out = []
        for i in range(rows):
            row = []
            for j in range(cols):
                row.append(0.0)
            out.append(row)
        return out
    def mat_set(M, i, j, v):
        target = row_at(M, i)
        tc = cp(target)
        new_row = []
        jj = 0
        while len(tc) > 0:
            old = tc.pop(0)
            if jj == j:
                new_row.append(v)
            else:
                new_row.append(old)
            jj = jj + 1
        if jj <= j:
            new_row.append(v)
        return replace_at(M, i, new_row)
    def matmul(A, B):
        m = 0
        for r in A:
            m = m + 1
        nb = 0
        for r in B:
            nb = nb + 1
        if m == 0 or nb == 0:
            return []
        b_first = row_at(B, 0)
        p = 0
        for v in b_first:
            p = p + 1
        # 关键: 用 list_acc 累积行 (避免 mat_set 反复重建 M)
        result = []
        for i in range(m):
            a_row = row_at(A, i)
            new_row = []
            for j in range(p):
                s = 0.0
                for k in range(nb):
                    arc = cp(a_row)
                    a_k = None
                    for _ in range(k + 1):
                        a_k = arc.pop(0)
                    b_kj = get_at(B, k, j)
                    s = s + a_k * b_kj
                new_row.append(s)
            result.append(new_row)
        return result
    def transpose(M):
        m = 0
        for r in M:
            m = m + 1
        if m == 0:
            return []
        n = 0
        for v in row_at(M, 0):
            n = n + 1
        out = zeros_mat(n, m)
        for i in range(m):
            for j in range(n):
                v = get_at(M, i, j)
                out = mat_set(out, j, i, v)
        return out
    def add_bias(M, b):
        b_row = row_at(b, 0)
        out = []
        for r in M:
            rc = cp(r)
            bc = cp(b_row)
            new_row = []
            while len(rc) > 0:
                a = rc.pop(0)
                bb = bc.pop(0)
                new_row.append(a + bb)
            out.append(new_row)
        return out
    def elem_sub(A, B):
        ac = cp(A)
        bc = cp(B)
        out = []
        while len(ac) > 0:
            ra = ac.pop(0)
            rb = bc.pop(0)
            rac = cp(ra)
            rbc = cp(rb)
            new_row = []
            while len(rac) > 0:
                a = rac.pop(0)
                b = rbc.pop(0)
                new_row.append(a - b)
            out.append(new_row)
        return out
    def elem_mul(A, B):
        ac = cp(A)
        bc = cp(B)
        out = []
        while len(ac) > 0:
            ra = ac.pop(0)
            rb = bc.pop(0)
            rac = cp(ra)
            rbc = cp(rb)
            new_row = []
            while len(rac) > 0:
                a = rac.pop(0)
                b = rbc.pop(0)
                new_row.append(a * b)
            out.append(new_row)
        return out
    def scale(M, s):
        out = []
        for r in M:
            rc = cp(r)
            new_row = []
            while len(rc) > 0:
                new_row.append(rc.pop(0) * s)
            out.append(new_row)
        return out
    def sum_axis0(M):
        m = 0
        for r in M:
            m = m + 1
        if m == 0:
            return []
        acc = cp(row_at(M, 0))
        for i in range(1, m):
            r = row_at(M, i)
            rc = cp(r)
            new_acc = []
            acc_c = cp(acc)
            while len(rc) > 0:
                a = acc_c.pop(0)
                b = rc.pop(0)
                new_acc.append(a + b)
            acc = new_acc
        return [acc]
    def myexp(x):
        if x > 50:
            return 1e20
        if x < -50:
            return 0.0
        ex = 0.0
        term = 1.0
        k = 0
        while k < 30:
            if k > 0:
                term = term * x / k
            ex = ex + term
            k = k + 1
        return ex
    def sig(x):
        if x >= 0:
            ex = myexp(-x)
        else:
            ex = 1.0 / myexp(x)
        return 1.0 / (1.0 + ex)
    def sigmoid(M):
        out = []
        for r in M:
            rc = cp(r)
            new_row = []
            while len(rc) > 0:
                new_row.append(sig(rc.pop(0)))
            out.append(new_row)
        return out
    def one_minus(M):
        out = []
        for r in M:
            rc = cp(r)
            new_row = []
            while len(rc) > 0:
                new_row.append(1.0 - rc.pop(0))
            out.append(new_row)
        return out
    # ---- forward ----
    n = 0
    for r in X:
        n = n + 1
    Z1 = add_bias(matmul(X, W1), b1)   # (4, 3)
    H = sigmoid(Z1)                     # (4, 3)
    Z2 = add_bias(matmul(H, W2), b2)   # (4, 1)
    O = sigmoid(Z2)                     # (4, 1)
    # ---- backward ----
    dO = scale(elem_sub(O, y), 1.0 / n)
    dH = elem_mul(elem_mul(matmul(dO, transpose(W2)), H), one_minus(H))
    dW1 = matmul(transpose(X), dH)
    db1 = sum_axis0(dH)
    dW2 = matmul(transpose(H), dO)
    db2 = sum_axis0(dO)
    return {"dW1": dW1, "db1": db1, "dW2": dW2, "db2": db2}
'''


# ============================================================
# 5. CNN conv2d — 全部用 pop, 无下标
# ============================================================
REFERENCE_CONV2D = '''
def conv2d(x, k):
    # x: HxW, k: m x m, return (H-m+1) x (W-m+1)
    H = 0
    for v in x:
        H = H + 1
    # 拿 x 第一行迭代得 W
    W = 0
    x_first = None
    x_tmp = []
    for v in x:
        x_tmp.append(v)
    if len(x_tmp) > 0:
        x_first = x_tmp.pop(0)
    if x_first is not None:
        for v in x_first:
            W = W + 1
    m = 0
    for v in k:
        m = m + 1
    out_h = H - m + 1
    out_w = W - m + 1
    k_rows = []
    for v in k:
        k_rows.append(v)
    result = []
    for i in range(out_h):
        row = []
        for j in range(out_w):
            s = 0.0
            for ki in range(m):
                for kj in range(m):
                    # 拿 x[i+ki][j+kj]
                    x_copy2 = []
                    for v in x:
                        x_copy2.append(v)
                    ti = None
                    for _ in range(i + ki + 1):
                        ti = x_copy2.pop(0)
                    ti_copy = []
                    for v in ti:
                        ti_copy.append(v)
                    xv = None
                    for _ in range(j + kj + 1):
                        xv = ti_copy.pop(0)
                    # 拿 k[ki][kj] (不动 k_rows, 复制拿)
                    k_copy = []
                    for v in k_rows:
                        k_copy.append(v)
                    kr = None
                    for _ in range(ki + 1):
                        kr = k_copy.pop(0)
                    kr_copy = []
                    for v in kr:
                        kr_copy.append(v)
                    kv = None
                    for _ in range(kj + 1):
                        kv = kr_copy.pop(0)
                    s = s + xv * kv
            row.append(s)
        result.append(row)
    return result
'''


# ============================================================
# 6. RNN BPTT — 全部用 pop
# ============================================================
REFERENCE_BPTT = '''
def bptt_dw(xs, W, U):
    def myexp(x):
        if x > 50:
            return 1e20
        if x < -50:
            return 0.0
        ex = 0.0
        term = 1.0
        k = 0
        while k < 40:
            if k > 0:
                term = term * x / k
            ex = ex + term
            k = k + 1
        return ex
    def tanh(x):
        if x > 50:
            return 1.0
        if x < -50:
            return -1.0
        e1 = myexp(x)
        e2 = myexp(-x)
        return (e1 - e2) / (e1 + e2)
    h = 0.0
    h_list = [0.0]  # h_0 = 0
    x_list = []
    for v in xs:
        x_list.append(v)
    while len(x_list) > 0:
        xt = x_list.pop(0)
        h = tanh(W * h + U * xt)
        h_list.append(h)
    dL_dh = 1.0
    dW = 0.0
    # 倒序遍历用 pop 链 (h_list 已经是 [h_0, h_1, ..., h_T])
    h_seq = []
    h_tmp = []
    for v in h_list:
        h_tmp.append(v)
    while len(h_tmp) > 0:
        h_seq.append(h_tmp.pop(0))
    h_t = h_seq.pop(0)  # h_0
    dL_dh_cur = 1.0
    while len(h_seq) > 0:
        h_prev = h_t
        h_t = h_seq.pop(0)
        one_minus = 1.0 - h_t * h_t
        dW = dW + dL_dh_cur * one_minus * h_prev
        dL_dh_cur = dL_dh_cur * one_minus * W
    return dW
'''


# ============================================================
# 7. Scaled Dot-Product Attention (本地 PASS, sandbox 需配合新 harness)
# ============================================================
REFERENCE_ATTENTION = '''
def scaled_dot_product_attention(Q, K, V):
    n = 0
    for v in Q:
        n = n + 1
    # 拿 Q 第一行迭代得 d_k (用 pop 不用下标)
    d_k = 0
    q_first = None
    q_tmp = []
    for v in Q:
        q_tmp.append(v)
    if len(q_tmp) > 0:
        q_first = q_tmp.pop(0)
    if q_first is not None:
        for v in q_first:
            d_k = d_k + 1
    scale = d_k ** 0.5
    K_T = []
    for j in range(d_k):
        col = []
        for i in range(n):
            k_copy = []
            for r in K:
                k_copy.append(r)
            row = None
            for _ in range(i + 1):
                row = k_copy.pop(0)
            row_copy = []
            for v in row:
                row_copy.append(v)
            v = None
            for _ in range(j + 1):
                v = row_copy.pop(0)
            col.append(v)
        K_T.append(col)
    scores = []
    for i in range(n):
        q_copy = []
        for r in Q:
            q_copy.append(r)
        q_row = None
        for _ in range(i + 1):
            q_row = q_copy.pop(0)
        row_scores = []
        for j in range(n):
            s = 0.0
            for k in range(d_k):
                q_copy2 = []
                for v in q_row:
                    q_copy2.append(v)
                qk = None
                for _ in range(k + 1):
                    qk = q_copy2.pop(0)
                k_t_copy = []
                for r in K_T:
                    k_t_copy.append(r)
                k_t_row = None
                for _ in range(k + 1):
                    k_t_row = k_t_copy.pop(0)
                k_t_row_copy = []
                for v in k_t_row:
                    k_t_row_copy.append(v)
                kv = None
                for _ in range(j + 1):
                    kv = k_t_row_copy.pop(0)
                s = s + qk * kv
            row_scores.append(s / scale)
        scores.append(row_scores)
    def myexp(x):
        if x > 50:
            return 1e20
        if x < -50:
            return 0.0
        ex = 0.0
        term = 1.0
        k = 0
        while k < 40:
            if k > 0:
                term = term * x / k
            ex = ex + term
            k = k + 1
        return ex
    softmax = []
    for row in scores:
        exps = []
        for v in row:
            exps.append(myexp(v))
        total = 0.0
        for v in exps:
            total = total + v
        sm_row = []
        for v in exps:
            sm_row.append(v / total)
        softmax.append(sm_row)
    attn = []
    for i in range(n):
        s_copy = []
        for r in softmax:
            s_copy.append(r)
        s_row = None
        for _ in range(i + 1):
            s_row = s_copy.pop(0)
        out_row = []
        for j in range(d_k):
            s = 0.0
            for k in range(n):
                s_copy2 = []
                for v in s_row:
                    s_copy2.append(v)
                sk = None
                for _ in range(k + 1):
                    sk = s_copy2.pop(0)
                v_copy = []
                for r in V:
                    v_copy.append(r)
                v_row = None
                for _ in range(k + 1):
                    v_row = v_copy.pop(0)
                v_row_copy = []
                for v in v_row:
                    v_row_copy.append(v)
                vv = None
                for _ in range(j + 1):
                    vv = v_row_copy.pop(0)
                s = s + sk * vv
            out_row.append(s)
        attn.append(out_row)
    return attn
'''


# ============================================================
# 8. RBF Kernel
# ============================================================
REFERENCE_RBF = '''
def rbf_kernel(x, y, gamma=0.5):
    xx = []
    yy = []
    for v in x:
        xx.append(v)
    for v in y:
        yy.append(v)
    s = 0.0
    while len(xx) > 0:
        a = xx.pop(0)
        b = yy.pop(0)
        d = a - b
        s = s + d * d
    arg = -gamma * s
    if arg < -50:
        return 0.0
    ex = 0.0
    term = 1.0
    k = 0
    while k < 60:
        if k > 0:
            term = term * arg / k
        ex = ex + term
        k = k + 1
    return ex
'''


REFERENCES = {
    "prog-ml_basics-knn-0704": REFERENCE_KNN,
    "prog-ml_basics-linreg-0704": REFERENCE_LINREG,
    "prog-decision_trees-id3-0704": REFERENCE_ID3,
    "prog-mlp-gradient-0704": REFERENCE_MLP,
    "prog-cnn-conv-0704": REFERENCE_CONV2D,
    "prog-rnn-bptt-0704": REFERENCE_BPTT,
    "prog-transformer-attn-0704": REFERENCE_ATTENTION,
    "prog-svm-kernel-0704": REFERENCE_RBF,
}
