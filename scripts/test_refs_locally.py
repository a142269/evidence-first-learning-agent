"""在普通 Python 跑 8 道题参考实现, 找逻辑 bug (不靠 sandbox)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.reference_solutions import REFERENCES

# 题 2 harness (普通 Python)
print("=== 题 2 LinReg ===")
try:
    exec(REFERENCES["prog-ml_basics-linreg-0704"], globals())
    w, b = globals()["linear_regression_gd"]([1,2,3,4,5], [2,4,6,8,10], lr=0.01, epochs=1000)
    print(f"  w={w:.4f} b={b:.4f}")
    print(f"  PASS: {abs(w - 2.0) < 0.5 and abs(b - 0.0) < 0.5}")
except Exception as e:
    import traceback
    traceback.print_exc()

# 题 3 ID3
print("\n=== 题 3 ID3 ===")
try:
    exec(REFERENCES["prog-decision_trees-id3-0704"], globals())
    # split_indices 是索引, group=[0,1] 意思取 labels[0], labels[1]
    ig = globals()["calc_info_gain"]([0,0,1,1], [[0,1],[2,3]])
    print(f"  ig1={ig:.6f}  expected ~1.0")
    ig2 = globals()["calc_info_gain"]([0,0,0,0], [[0,1,2,3]])
    print(f"  ig2={ig2:.6f}  expected ~0.0")
except Exception as e:
    import traceback
    traceback.print_exc()

# 题 4 MLP
print("\n=== 题 4 MLP ===")
try:
    exec(REFERENCES["prog-mlp-gradient-0704"], globals())
    import math
    # 简单测试: X 1x2, y 1x1
    X = [[0.5, 0.3]]
    y = [[1]]
    W1 = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    b1 = [[0, 0, 0]]
    W2 = [[0.1], [0.2], [0.3]]
    b2 = [[0]]
    grads = globals()["mlp_forward_backward"](X, y, W1, b1, W2, b2)
    print(f"  dW1 shape: {len(grads['dW1'])}x{len(grads['dW1'][0])}")
    print(f"  dW2 shape: {len(grads['dW2'])}x{len(grads['dW2'][0])}")
except Exception as e:
    import traceback
    traceback.print_exc()

# 题 5 CNN
print("\n=== 题 5 CNN ===")
try:
    exec(REFERENCES["prog-cnn-conv-0704"], globals())
    x = [[1,2,3],[4,5,6],[7,8,9]]
    k = [[1,0],[0,-1]]
    out = globals()["conv2d"](x, k)
    print(f"  out={out}")
    print(f"  PASS: {out == [[-4, -4], [-4, -4]]}")
except Exception as e:
    import traceback
    traceback.print_exc()

# 题 6 RNN
print("\n=== 题 6 RNN ===")
try:
    exec(REFERENCES["prog-rnn-bptt-0704"], globals())
    dW = globals()["bptt_dw"]([1.0, 2.0, 3.0], 0.5, 1.0)
    print(f"  dW={dW}")
    print(f"  PASS: isinstance(dW, float) and -1e308 < dW < 1e308")
except Exception as e:
    import traceback
    traceback.print_exc()

# 题 7 Attn
print("\n=== 题 7 Attn ===")
try:
    exec(REFERENCES["prog-transformer-attn-0704"], globals())
    Q = [[1.0, 0.0], [0.0, 1.0]]
    K = [[1.0, 0.0], [0.0, 1.0]]
    V = [[1.0, 0.0], [0.0, 1.0]]
    out = globals()["scaled_dot_product_attention"](Q, K, V)
    print(f"  out={out}")
    print(f"  out[0][0]={out[0][0]:.4f}  out[1][1]={out[1][1]:.4f}")
except Exception as e:
    import traceback
    traceback.print_exc()

# 题 8 RBF (已知 PASS)
print("\n=== 题 8 RBF ===")
try:
    exec(REFERENCES["prog-svm-kernel-0704"], globals())
    v1 = globals()["rbf_kernel"]([1,2], [1,2])
    v2 = globals()["rbf_kernel"]([0,0], [10,10], gamma=0.5)
    print(f"  v1={v1} v2={v2}")
    print(f"  PASS: {abs(v1 - 1.0) < 1e-6 and v2 < 1e-3}")
except Exception as e:
    import traceback
    traceback.print_exc()
