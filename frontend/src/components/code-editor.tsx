"use client";

import { cpp } from "@codemirror/lang-cpp";
import { go } from "@codemirror/lang-go";
import { java } from "@codemirror/lang-java";
import { javascript } from "@codemirror/lang-javascript";
import { php } from "@codemirror/lang-php";
import { python } from "@codemirror/lang-python";
import { rust } from "@codemirror/lang-rust";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorView, keymap } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import CodeMirror, { type Extension } from "@uiw/react-codemirror";
import { useMemo } from "react";

const LANGUAGES: Record<string, () => Extension> = {
  python: () => python(),
  javascript: () => javascript(),
  typescript: () => javascript({ typescript: true }),
  java: () => java(),
  go: () => go(),
  csharp: () => java(), // close enough for highlighting
  cpp: () => cpp(),
  rust: () => rust(),
  php: () => php({ plain: true }),
};

// colours come from the app's CSS variables, so the editor follows the light and dark themes
const theme = EditorView.theme({
  "&": { backgroundColor: "transparent", color: "var(--foreground)", fontSize: "12.5px" },
  "&.cm-focused": { outline: "none" },
  ".cm-content": { fontFamily: "var(--font-mono)", padding: "10px 0", caretColor: "var(--primary)" },
  ".cm-scroller": { fontFamily: "var(--font-mono)", lineHeight: "1.65" },
  ".cm-gutters": {
    backgroundColor: "transparent",
    color: "var(--muted-foreground)",
    border: "none",
    paddingLeft: "6px",
    opacity: "0.55",
  },
  ".cm-activeLine": { backgroundColor: "color-mix(in oklab, var(--muted) 45%, transparent)" },
  ".cm-activeLineGutter": { backgroundColor: "transparent", color: "var(--foreground)" },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground, ::selection": {
    backgroundColor: "color-mix(in oklab, var(--primary) 28%, transparent) !important",
  },
  ".cm-placeholder": { color: "var(--muted-foreground)", fontStyle: "normal" },
  ".cm-cursor": { borderLeftColor: "var(--primary)" },
});

const highlight = syntaxHighlighting(
  HighlightStyle.define([
    { tag: [t.keyword, t.controlKeyword, t.operatorKeyword, t.modifier], color: "var(--code-keyword)" },
    { tag: [t.string, t.special(t.string)], color: "var(--code-string)" },
    { tag: [t.number, t.bool, t.null], color: "var(--code-number)" },
    { tag: [t.comment, t.lineComment, t.blockComment], color: "var(--muted-foreground)", fontStyle: "italic" },
    { tag: [t.function(t.variableName), t.function(t.definition(t.variableName))], color: "var(--code-function)" },
    { tag: [t.definition(t.variableName), t.className, t.typeName], color: "var(--code-type)" },
  ]),
);

export function CodeEditor({
  value,
  onChange,
  language,
  placeholder,
  minHeight,
  onSubmit,
}: {
  value: string;
  onChange: (v: string) => void;
  language: string;
  placeholder?: string;
  minHeight: string;
  onSubmit?: () => void;
}) {
  const extensions = useMemo(() => {
    const ext: Extension[] = [theme, highlight, EditorView.lineWrapping];
    const lang = LANGUAGES[language];
    if (lang) ext.push(lang());
    if (onSubmit)
      ext.push(
        keymap.of([
          {
            key: "Mod-Enter",
            run: () => {
              onSubmit();
              return true;
            },
          },
        ]),
      );
    return ext;
  }, [language, onSubmit]);
  return (
    <div className="overflow-hidden rounded-lg border bg-card transition-shadow focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/30">
      <CodeMirror
        value={value}
        onChange={onChange}
        extensions={extensions}
        placeholder={placeholder}
        minHeight={minHeight}
        maxHeight="420px"
        theme="none"
        basicSetup={{
          foldGutter: false,
          highlightActiveLine: true,
          autocompletion: false,
          searchKeymap: false,
          highlightSelectionMatches: false,
        }}
        indentWithTab
      />
    </div>
  );
}
