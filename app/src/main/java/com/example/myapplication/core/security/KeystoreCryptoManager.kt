package com.example.myapplication.core.security

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.nio.ByteBuffer
import java.security.InvalidKeyException
import java.security.KeyStore
import java.security.UnrecoverableKeyException
import java.util.Base64
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Encrypts and decrypts persisted credential payloads using an AES-256-GCM key stored in
 * the hardware-backed Android Keystore (`AndroidKeyStore`).
 *
 * Resilience:
 * - Detects `InvalidKeyException`, `KeyPermanentlyInvalidatedException`, or corrupted keys.
 * - Safely deletes the invalidated key and regenerates a fresh AES-256 key in AndroidKeyStore.
 * - Re-encrypts payload under the new key so active sessions are not lost unless recovery is impossible.
 * - Never returns or persists plaintext data.
 */
@Singleton
open class KeystoreCryptoManager @Inject constructor() {

    open fun encrypt(plaintext: String): String {
        return try {
            encryptWithKey(plaintext, getOrCreateSecretKey())
        } catch (ex: Exception) {
            if (isKeyInvalidationException(ex)) {
                // Key is invalid or permanently invalidated.
                // Safely delete and regenerate the key, then re-attempt encryption.
                deleteKey()
                val newKey = generateNewSecretKey()
                encryptWithKey(plaintext, newKey)
            } else {
                throw ex
            }
        }
    }

    protected open fun encryptWithKey(plaintext: String, secretKey: SecretKey): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, secretKey)
        val iv = cipher.iv
        val ciphertext = cipher.doFinal(plaintext.toByteArray(Charsets.UTF_8))

        val packed = ByteBuffer.allocate(4 + iv.size + ciphertext.size)
            .putInt(iv.size)
            .put(iv)
            .put(ciphertext)
            .array()

        return Base64.getEncoder().encodeToString(packed)
    }

    open fun decrypt(encodedPayload: String): String? {
        return try {
            val packed = Base64.getDecoder().decode(encodedPayload)
            val buffer = ByteBuffer.wrap(packed)
            val ivSize = buffer.int
            if (ivSize <= 0 || ivSize > 32 || buffer.remaining() <= ivSize) {
                return null
            }
            val iv = ByteArray(ivSize)
            buffer.get(iv)
            val ciphertext = ByteArray(buffer.remaining())
            buffer.get(ciphertext)

            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(
                Cipher.DECRYPT_MODE,
                getOrCreateSecretKey(),
                GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv)
            )
            String(cipher.doFinal(ciphertext), Charsets.UTF_8)
        } catch (_: Exception) {
            null
        }
    }

    open fun deleteKey() {
        try {
            val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
            if (keyStore.containsAlias(KEY_ALIAS)) {
                keyStore.deleteEntry(KEY_ALIAS)
            }
        } catch (_: Exception) {
            // Ignore key deletion errors
        }
    }

    open fun regenerateKey(): SecretKey {
        deleteKey()
        return generateNewSecretKey()
    }

    protected open fun getOrCreateSecretKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        val existingKey = keyStore.getKey(KEY_ALIAS, null) as? SecretKey
        if (existingKey != null) {
            return existingKey
        }
        return generateNewSecretKey()
    }

    protected open fun generateNewSecretKey(): SecretKey {
        val keyGenerator = KeyGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_AES,
            ANDROID_KEYSTORE
        )
        val spec = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .setRandomizedEncryptionRequired(true)
            .build()

        keyGenerator.init(spec)
        return keyGenerator.generateKey()
    }

    fun isKeyInvalidationException(throwable: Throwable): Boolean {
        var current: Throwable? = throwable
        while (current != null) {
            if (current is InvalidKeyException ||
                current is UnrecoverableKeyException ||
                current.javaClass.name.contains("KeyPermanentlyInvalidatedException")
            ) {
                return true
            }
            current = current.cause
        }
        return false
    }

    companion object {
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val KEY_ALIAS = "fieldshift_session_aes_key"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val GCM_TAG_LENGTH_BITS = 128
    }
}
