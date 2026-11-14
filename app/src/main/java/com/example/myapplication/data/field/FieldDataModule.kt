package com.example.myapplication.data.field

import com.example.myapplication.domain.field.FieldRepository
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
abstract class FieldDataModule {

    @Binds
    @Singleton
    abstract fun bindFieldRepository(impl: FieldRepositoryImpl): FieldRepository
}

