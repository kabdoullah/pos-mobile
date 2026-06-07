/// Utilitaires de formatage des numéros de téléphone ivoiriens.
///
/// Format attendu en saisie : 10 chiffres commençant par 0 (ex : 0700000000).
/// Format backend (E.164) : +225 suivi des 10 chiffres (ex : +2250700000000).
/// Format affichage      : +225 07 00 00 00 00 (espaces tous les 2 chiffres).
library;

import 'package:flutter/services.dart';

/// Convertit un numéro local CI (0XXXXXXXXX) en E.164 (+225XXXXXXXXXX).
///
/// Supprime les espaces et tirets avant conversion.
/// Retourne null si le format d'entrée n'est pas reconnu.
String? toE164Ci(String localNumber) {
  final digits = localNumber.replaceAll(RegExp(r'[\s\-]'), '');
  if (RegExp(r'^0\d{9}$').hasMatch(digits)) {
    return '+225$digits';
  }
  // Déjà en E.164 (+225XXXXXXXXXX).
  if (RegExp(r'^\+225\d{10}$').hasMatch(digits)) {
    return digits;
  }
  return null;
}

/// Formate un numéro E.164 CI pour l'affichage.
///
/// `+2250700000000` → `+225 07 00 00 00 00`
String formatPhoneCiDisplay(String e164) {
  if (!e164.startsWith('+225') || e164.length < 6) return e164;
  final local = e164.substring(4); // chiffres après +225
  final spaced = StringBuffer();
  for (var i = 0; i < local.length; i += 2) {
    if (spaced.isNotEmpty) spaced.write(' ');
    final end = (i + 2).clamp(0, local.length);
    spaced.write(local.substring(i, end));
  }
  return '+225 $spaced';
}

/// Valide un numéro en format local CI : exactement 10 chiffres commençant par 0.
bool isValidLocalPhoneCi(String localNumber) {
  final digits = localNumber.replaceAll(RegExp(r'[\s\-]'), '');
  return RegExp(r'^0\d{9}$').hasMatch(digits);
}

/// Formate la saisie d'un numéro ivoirien en paires espacées : `07 07 07 07 07`.
///
/// À utiliser dans `inputFormatters` d'un [TextField] téléphone.
/// Préserve la position curseur lors des éditions en milieu de champ.
class SpacedPhoneFormatter extends TextInputFormatter {
  /// Permet `const [SpacedPhoneFormatter()]` dans inputFormatters.
  const SpacedPhoneFormatter();

  static const _maxDigits = 10;

  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digits = newValue.text.replaceAll(RegExp(r'\D'), '');
    final truncated =
        digits.length > _maxDigits ? digits.substring(0, _maxDigits) : digits;

    final buffer = StringBuffer();
    for (var i = 0; i < truncated.length; i++) {
      buffer.write(truncated[i]);
      if ((i + 1) % 2 == 0 && i + 1 != truncated.length) {
        buffer.write(' ');
      }
    }
    final formatted = buffer.toString();

    // Mapper la position curseur par compte de chiffres — pas par offset brut.
    // Sans ça, toute édition en milieu de champ téléporte le curseur en fin.
    final selEnd = newValue.selection.end.clamp(0, newValue.text.length);
    final digitsBeforeCursor = newValue.text
        .substring(0, selEnd)
        .replaceAll(RegExp(r'\D'), '')
        .length
        .clamp(0, truncated.length);

    var cursorOffset = 0;
    var digitsSeen = 0;
    for (var i = 0; i < formatted.length; i++) {
      if (digitsSeen == digitsBeforeCursor) break;
      if (formatted[i] != ' ') digitsSeen++;
      cursorOffset = i + 1;
    }

    return TextEditingValue(
      text: formatted,
      selection: TextSelection.collapsed(offset: cursorOffset),
    );
  }
}
