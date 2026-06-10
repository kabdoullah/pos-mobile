/// Strips ASCII control characters and leading/trailing whitespace from a raw
/// barcode value (handles GS1 FNC1 and similar scanner artefacts).
/// Returns null if the result is empty, the input is null, or the result does
/// not satisfy the server-side validation pattern (alphanumeric, 6–50 chars).
String? normalizeBarcode(String? raw) {
  if (raw == null) return null;
  final cleaned = raw.trim().replaceAll(RegExp(r'[\x00-\x1F\x7F]'), '');
  if (cleaned.isEmpty) return null;
  // Server rejects barcodes that don't match ^[A-Za-z0-9]{6,50}$.
  // Discard silently to avoid push failures (422) that loop forever.
  if (!RegExp(r'^[A-Za-z0-9]{6,50}$').hasMatch(cleaned)) return null;
  return cleaned;
}
