package com.idea_finder.repo.domain;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

@Converter
public class SourcePlatformConverter implements AttributeConverter<SourcePlatform, String> {

	@Override
	public String convertToDatabaseColumn(SourcePlatform attribute) {
		return attribute == null ? null : attribute.dbValue();
	}

	@Override
	public SourcePlatform convertToEntityAttribute(String dbData) {
		return dbData == null ? null : SourcePlatform.fromDbValue(dbData);
	}
}
