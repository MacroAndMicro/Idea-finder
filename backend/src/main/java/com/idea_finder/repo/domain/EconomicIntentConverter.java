package com.idea_finder.repo.domain;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

@Converter
public class EconomicIntentConverter implements AttributeConverter<EconomicIntent, String> {

	@Override
	public String convertToDatabaseColumn(EconomicIntent attribute) {
		return attribute == null ? null : attribute.dbValue();
	}

	@Override
	public EconomicIntent convertToEntityAttribute(String dbData) {
		return dbData == null ? null : EconomicIntent.fromDbValue(dbData);
	}
}
