import 'package:freezed_annotation/freezed_annotation.dart';
import 'package:json_annotation/json_annotation.dart';

part 'auth_models.freezed.dart';
part 'auth_models.g.dart';

/// Request payload for user registration.
@freezed
sealed class RegisterRequestDto with _$RegisterRequestDto {
  /// Creates a RegisterRequestDto.
  const factory RegisterRequestDto({
    required String email,
    required String password,
    @JsonKey(name: 'phone_number') required String phoneNumber,
  }) = _RegisterRequestDto;

  factory RegisterRequestDto.fromJson(Map<String, dynamic> json) =>
      _$RegisterRequestDtoFromJson(json);
}

/// Response after successful registration.
@freezed
sealed class RegisterResponseDto with _$RegisterResponseDto {
  /// Creates a RegisterResponseDto.
  const factory RegisterResponseDto({
    @JsonKey(name: 'user_id') required String userId,
    required String email,
    required String message,
  }) = _RegisterResponseDto;

  factory RegisterResponseDto.fromJson(Map<String, dynamic> json) =>
      _$RegisterResponseDtoFromJson(json);
}

/// Request payload for login.
@freezed
sealed class LoginRequestDto with _$LoginRequestDto {
  /// Creates a LoginRequestDto.
  const factory LoginRequestDto({
    required String email,
    required String password,
  }) = _LoginRequestDto;

  factory LoginRequestDto.fromJson(Map<String, dynamic> json) =>
      _$LoginRequestDtoFromJson(json);
}

/// Response containing access and refresh tokens.
@freezed
sealed class TokenResponseDto with _$TokenResponseDto {
  /// Creates a TokenResponseDto.
  const factory TokenResponseDto({
    @JsonKey(name: 'access_token') required String accessToken,
    @JsonKey(name: 'refresh_token') required String refreshToken,
    @JsonKey(name: 'token_type') required String tokenType,
    @JsonKey(name: 'expires_in') required int expiresIn,
  }) = _TokenResponseDto;

  factory TokenResponseDto.fromJson(Map<String, dynamic> json) =>
      _$TokenResponseDtoFromJson(json);
}

/// Request payload for password reset request.
@freezed
sealed class ForgotPasswordRequestDto with _$ForgotPasswordRequestDto {
  /// Creates a ForgotPasswordRequestDto.
  const factory ForgotPasswordRequestDto({required String email}) =
      _ForgotPasswordRequestDto;

  factory ForgotPasswordRequestDto.fromJson(Map<String, dynamic> json) =>
      _$ForgotPasswordRequestDtoFromJson(json);
}

/// Request payload for confirming password reset.
@freezed
sealed class ResetPasswordRequestDto with _$ResetPasswordRequestDto {
  /// Creates a ResetPasswordRequestDto.
  const factory ResetPasswordRequestDto({
    required String token,
    @JsonKey(name: 'new_password') required String newPassword,
  }) = _ResetPasswordRequestDto;

  factory ResetPasswordRequestDto.fromJson(Map<String, dynamic> json) =>
      _$ResetPasswordRequestDtoFromJson(json);
}
