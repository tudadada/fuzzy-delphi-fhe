// ---------------------------------------------------------------------------
// fdfhe: extra bindings appended to openfhe-wasm's src/pke/CryptoContext_em.cpp
// (appended, not a separate translation unit, because the upstream headers define
// non-inline helpers that would clash at link time).
//
// Adds what a 3-member key ceremony needs and upstream does not expose:
//   multiparty rotation keys, automorphism key maps, and EvalKey / key-map serialization.
// ---------------------------------------------------------------------------
#include <cereal/types/map.hpp>
#include <cereal/types/memory.hpp>

using FdKeyMap = std::map<uint32_t, EvalKey<DCRTPoly>>;
using FdKeyMapPtr = std::shared_ptr<FdKeyMap>;

FdKeyMapPtr FdGetEvalAutomorphismKeyMap(const CryptoContext<DCRTPoly>& cc, const std::string& keyTag) {
  return std::make_shared<FdKeyMap>(cc->GetEvalAutomorphismKeyMap(keyTag));
}

FdKeyMapPtr FdMultiEvalAtIndexKeyGen(const CryptoContext<DCRTPoly>& cc, const PrivateKey<DCRTPoly> sk,
                                     const FdKeyMapPtr prev, const emscripten::val& indexList,
                                     const std::string& keyTag) {
  auto idx = vecFromJSArray<int32_t>(indexList);
  return cc->MultiEvalAtIndexKeyGen(sk, prev, idx, keyTag);
}

FdKeyMapPtr FdMultiAddEvalAutomorphismKeys(const CryptoContext<DCRTPoly>& cc, const FdKeyMapPtr a,
                                           const FdKeyMapPtr b, const std::string& keyTag) {
  return cc->MultiAddEvalAutomorphismKeys(a, b, keyTag);
}

void FdInsertEvalAutomorphismKey(const CryptoContext<DCRTPoly>& cc, const FdKeyMapPtr m) {
  CryptoContextImpl<DCRTPoly>::InsertEvalAutomorphismKey(m);
}

emscripten::val FdSerializeKeyMap(const FdKeyMapPtr m, JsSerType serType) {
  std::ostringstream os;
  if (serType == JsSerType::BINARY) {
    cereal::PortableBinaryOutputArchive ar(os);
    ar(*m);
  } else {
    cereal::JSONOutputArchive ar(os);
    ar(*m);
  }
  return stringstreamToTypedArray(os);
}

FdKeyMapPtr FdDeserializeKeyMap(const emscripten::val& jsBuf, JsSerType serType) {
  auto is = typedArrayToStringstream(jsBuf);
  auto m = std::make_shared<FdKeyMap>();
  if (serType == JsSerType::BINARY) {
    cereal::PortableBinaryInputArchive ar(is);
    ar(*m);
  } else {
    cereal::JSONInputArchive ar(is);
    ar(*m);
  }
  return m;
}

// Smaller partial decryptions: drop RNS towers we don't need before decrypting.
Ciphertext<DCRTPoly> FdCompress(const CryptoContext<DCRTPoly>& cc, Ciphertext<DCRTPoly> ct, uint32_t towersLeft) {
  return cc->Compress(ct, towersLeft);
}

EMSCRIPTEN_BINDINGS(fdfhe_extra) {
  emscripten::function("FdGetEvalAutomorphismKeyMap", &FdGetEvalAutomorphismKeyMap);
  emscripten::function("FdMultiEvalAtIndexKeyGen", &FdMultiEvalAtIndexKeyGen);
  emscripten::function("FdMultiAddEvalAutomorphismKeys", &FdMultiAddEvalAutomorphismKeys);
  emscripten::function("FdInsertEvalAutomorphismKey", &FdInsertEvalAutomorphismKey);
  emscripten::function("FdSerializeKeyMap", &FdSerializeKeyMap);
  emscripten::function("FdDeserializeKeyMap", &FdDeserializeKeyMap);
  emscripten::function("FdSerializeEvalKey", &SerializeToBuffer<EvalKey<DCRTPoly>>);
  emscripten::function("FdDeserializeEvalKey", &DeserializeFromBuffer<EvalKey<DCRTPoly>>);
  emscripten::function("FdCompress", &FdCompress);
}
