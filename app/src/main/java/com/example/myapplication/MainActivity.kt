package com.example.myapplication

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.example.myapplication.core.designsystem.theme.FieldShiftTheme
import com.example.myapplication.core.network.ApiEndpointConfig
import com.example.myapplication.navigation.FieldShiftAppShell
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject
    lateinit var apiEndpointConfig: ApiEndpointConfig

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            FieldShiftTheme {
                FieldShiftAppShell(apiEndpointConfig = apiEndpointConfig)
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun FieldShiftAppPreview() {
    FieldShiftTheme {
        FieldShiftAppShell(
            apiEndpointConfig = ApiEndpointConfig(rawBaseUrl = BuildConfig.API_BASE_URL)
        )
    }
}
