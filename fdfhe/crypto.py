"""OpenFHE context shared by every role. Parameters must match on every machine."""
from openfhe import CCParamsBFVRNS, GenCryptoContext, MultipartyMode, PKESchemeFeature
from .params import P, LV, MULT_DEPTH


def make_params():
    p = CCParamsBFVRNS()
    p.SetPlaintextModulus(P)
    p.SetMultiplicativeDepth(MULT_DEPTH)
    p.SetMultipartyMode(MultipartyMode.NOISE_FLOODING_MULTIPARTY)
    return p


def make_context():
    cc = GenCryptoContext(make_params())
    for f in (PKESchemeFeature.PKE, PKESchemeFeature.KEYSWITCH, PKESchemeFeature.LEVELEDSHE,
              PKESchemeFeature.ADVANCEDSHE, PKESchemeFeature.MULTIPARTY):
        cc.Enable(f)
    return cc


def rotation_indices(K: int):
    return [l * K for l in range(1, LV)]


def packed(cc, values):
    """Packed plaintext, zero-padded to the full slot count."""
    slots = cc.GetRingDimension()
    vals = [int(v) for v in values]
    if len(vals) > slots:
        raise ValueError(f"{len(vals)} values do not fit in {slots} slots")
    return cc.MakePackedPlaintext(vals + [0] * (slots - len(vals)))


def level_sum(cc, ct, K: int):
    """Slot k of the result = sum over levels of slot l*K + k."""
    acc = ct
    for l in range(1, LV):
        acc = cc.EvalAdd(acc, cc.EvalRotate(ct, l * K))
    return acc


def max_criteria(cc) -> int:
    return cc.GetRingDimension() // LV
