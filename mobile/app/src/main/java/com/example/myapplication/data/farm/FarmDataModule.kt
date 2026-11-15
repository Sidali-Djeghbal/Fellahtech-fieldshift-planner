package com.example.myapplication.data.farm

import com.example.myapplication.domain.farm.FarmRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class FarmDataModule {

    @Binds
    @Singleton
    abstract fun bindFarmRepository(impl: FarmRepositoryImpl): FarmRepository
}

