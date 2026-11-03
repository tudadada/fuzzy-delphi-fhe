"""So sánh chế độ giải mã nhiều bên của OpenFHE: FIXED_NOISE (mặc định) và NOISE_FLOODING (khuyến nghị).
Chạy lại toàn bộ phép thử của v0.3 (07_public_validity.py) dưới từng chế độ. Xem SECURITY.md, Gap G2."""
import importlib.util, os, sys, time
from openfhe import *
here = os.path.dirname(__file__)
spec = importlib.util.spec_from_file_location("v03", os.path.join(here, "07_public_validity.py"))
v03 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v03)
_orig = v03.v02.CCParamsBFVRNS
for mode in ("FIXED_NOISE_MULTIPARTY", "NOISE_FLOODING_MULTIPARTY"):
    def params(m=mode):
        p = _orig(); p.SetMultipartyMode(getattr(MultipartyMode, m)); return p
    v03.v02.CCParamsBFVRNS = params
    t = time.time(); r = v03.run(20, 30); dt = time.time() - t
    com = v03.Committee(3, 2, 30); cc = com.cc
    up = len(Serialize(cc.Encrypt(com.pk, cc.MakePackedPlaintext([1]*30)), BINARY)) / 1024
    ok = all(r[k] for k in ("catches_all_3", "no_false_positive", "audit_validity_matches", "exact"))
    print(f"{mode}: N={cc.GetRingDimension()} | upload {up:.0f} KB | total {dt:.1f} s | all checks {'pass' if ok else 'FAIL'}")
