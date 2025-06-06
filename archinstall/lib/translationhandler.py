from __future__ import annotations

import builtins
import gettext
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import override


@dataclass
class Language:
	abbr: str
	name_en: str
	translation: gettext.NullTranslations
	translation_percent: int
	translated_lang: str | None

	@property
	def display_name(self) -> str:
		name = self.name_en
		return f'{name} ({self.translation_percent}%)'

	def is_match(self, lang_or_translated_lang: str) -> bool:
		if self.name_en == lang_or_translated_lang:
			return True
		elif self.translated_lang == lang_or_translated_lang:
			return True
		return False

	def json(self) -> str:
		return self.name_en


class TranslationHandler:
	def __init__(self) -> None:
		self._base_pot = 'base.pot'
		self._languages = 'languages.json'

		self._total_messages = self._get_total_active_messages()
		self._translated_languages = self._get_translations()

	@property
	def translated_languages(self) -> list[Language]:
		return self._translated_languages

	def _get_translations(self) -> list[Language]:
		"""
		Load all translated languages and return a list of such
		"""
		mappings = self._load_language_mappings()
		defined_languages = self._provided_translations()

		languages = []

		for short_form in defined_languages:
			mapping_entry: dict[str, str] = next(filter(lambda x: x['abbr'] == short_form, mappings))
			abbr = mapping_entry['abbr']
			lang = mapping_entry['lang']
			translated_lang = mapping_entry.get('translated_lang', None)

			try:
				# get a translation for a specific language
				translation = gettext.translation('base', localedir=self._get_locales_dir(), languages=(abbr, lang))

				# calculate the percentage of total translated text to total number of messages
				if abbr == 'en':
					percent = 100
				else:
					num_translations = self._get_catalog_size(translation)
					percent = int((num_translations / self._total_messages) * 100)
					# prevent cases where the .pot file is out of date and the percentage is above 100
					percent = min(100, percent)

				language = Language(abbr, lang, translation, percent, translated_lang)
				languages.append(language)
			except FileNotFoundError as err:
				raise FileNotFoundError(f"Could not locate language file for '{lang}': {err}")

		return languages

	def _load_language_mappings(self) -> list[dict[str, str]]:
		"""
		Load the mapping table of all known languages
		"""
		locales_dir = self._get_locales_dir()
		languages = Path.joinpath(locales_dir, self._languages)

		with open(languages) as fp:
			return json.load(fp)

	def _get_catalog_size(self, translation: gettext.NullTranslations) -> int:
		"""
		Get the number of translated messages for a translations
		"""
		# this is a very naughty way of retrieving the data but
		# there's no alternative method exposed unfortunately
		catalog = translation._catalog  # type: ignore[attr-defined]
		messages = {k: v for k, v in catalog.items() if k and v}
		return len(messages)

	def _get_total_active_messages(self) -> int:
		"""
		Get total messages that could be translated
		"""
		locales = self._get_locales_dir()
		with open(f'{locales}/{self._base_pot}') as fp:
			lines = fp.readlines()
			msgid_lines = [line for line in lines if 'msgid' in line]

		return len(msgid_lines) - 1  # don't count the first line which contains the metadata

	def get_language_by_name(self, name: str) -> Language:
		"""
		Get a language object by it's name, e.g. English
		"""
		try:
			return next(filter(lambda x: x.name_en == name, self._translated_languages))
		except Exception:
			raise ValueError(f'No language with name found: {name}')

	def get_language_by_abbr(self, abbr: str) -> Language:
		"""
		Get a language object by its abbreviation, e.g. en
		"""
		try:
			return next(filter(lambda x: x.abbr == abbr, self._translated_languages))
		except Exception:
			raise ValueError(f'No language with abbreviation "{abbr}" found')

	def activate(self, language: Language) -> None:
		"""
		Set the provided language as the current translation
		"""
		# The install() call has the side effect of assigning GNUTranslations.gettext to builtins._
		language.translation.install()

	def _get_locales_dir(self) -> Path:
		"""
		Get the locales directory path
		"""
		cur_path = Path(__file__).parent.parent
		locales_dir = Path.joinpath(cur_path, 'locales')
		return locales_dir

	def _provided_translations(self) -> list[str]:
		"""
		Get a list of all known languages
		"""
		locales_dir = self._get_locales_dir()
		filenames = os.listdir(locales_dir)

		translation_files = []
		for filename in filenames:
			if len(filename) == 2 or filename in ['pt_BR', 'zh-CN', 'zh-TW']:
				translation_files.append(filename)

		return translation_files


class _DeferredTranslation:
	def __init__(self, message: str):
		self.message = message

	@override
	def __str__(self) -> str:
		if builtins._ is _DeferredTranslation:  # type: ignore[attr-defined]
			return self.message

		# builtins._ is changed from _DeferredTranslation to GNUTranslations.gettext after
		# Language.activate() is called
		return builtins._(self.message)  # type: ignore[attr-defined]


def tr(message: str) -> str:
	return str(_DeferredTranslation(message))


builtins._ = _DeferredTranslation  # type: ignore[attr-defined]


translation_handler = TranslationHandler()
