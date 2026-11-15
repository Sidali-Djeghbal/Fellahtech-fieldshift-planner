package com.example.myapplication.data.analysis

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import com.example.myapplication.domain.analysis.AnalysisRepository
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class AnalysisDataModule {

    @Binds
    @Singleton
    abstract fun bindActiveAnalysisStore(
        impl: DataStoreActiveAnalysisStore
    ): ActiveAnalysisStore

    @Binds
    @Singleton
    abstract fun bindAnalysisRepository(
        impl: AnalysisRepositoryImpl
    ): AnalysisRepository

    companion object {
        @Provides
        @Singleton
        @ActiveAnalysisDataStore
        fun provideActiveAnalysisDataStore(
            @ApplicationContext context: Context
        ): DataStore<Preferences> = DataStoreActiveAnalysisStore.createDataStore(context)
    }
}

