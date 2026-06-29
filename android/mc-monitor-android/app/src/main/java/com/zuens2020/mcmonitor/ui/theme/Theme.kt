package com.zuens2020.mcmonitor.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Green = Color(0xFF2E7D32)
private val GreenDark = Color(0xFF1B5E20)

private val LightColors = lightColorScheme(
    primary = Green,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFC8E6C9),
    onPrimaryContainer = GreenDark,
    secondary = Color(0xFF546E7A),
    tertiary = Color(0xFF6A1B9A),
    error = Color(0xFFC62828),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF81C784),
    onPrimary = Color(0xFF003300),
    primaryContainer = GreenDark,
    onPrimaryContainer = Color(0xFFC8E6C9),
    secondary = Color(0xFF90A4AE),
    tertiary = Color(0xFFCE93D8),
    error = Color(0xFFEF5350),
)

@Composable
fun McMonitorTheme(darkTheme: Boolean, content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
