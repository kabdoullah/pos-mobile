import 'package:freezed_annotation/freezed_annotation.dart';

part 'user.freezed.dart';

/// Entité métier représentant un utilisateur connecté.
///
/// Immutable. Construite uniquement après authentification réussie.
@freezed
sealed class User with _$User {
  /// Constructor.
  const factory User({
    required String id,
    required String phoneNumber,
    String? email,
    String? storeId,
    DateTime? emailVerifiedAt,
  }) = _User;
}
