/// Strips ASCII control characters and leading/trailing whitespace from a raw
/// barcode value (handles GS1 FNC1 and similar scanner artefacts).
/// Returns null if the result is empty or the input is null.
String? normalizeBarcode(String? raw) {
  if (raw == null) return null;
  final cleaned = raw.trim().replaceAll(RegExp(r'[\x00-\x1F\x7F]'), '');
  return cleaned.isEmpty ? null : cleaned;
}
