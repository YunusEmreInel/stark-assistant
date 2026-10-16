"""Hafıza komutlarını uygular ve Stark'ın söyleyeceği cevabı üretir."""
from .commands import MemoryCommand
from .database import KNOWLEDGE, Repository

LIST_SPOKEN_MAX = 5

TEXT = {
    "tr": {
        "saved": "Tamamdır patron, hafızama kaydettim.",
        "noted": "Not aldım patron.",
        "no_notes": "Henüz notunuz yok patron. “Not al” diyerek ekleyebilirsiniz.",
        "notes": "{n} notunuz var patron. Son notlarınız: {items}",
        "note_deleted": "Son notu sildim patron: {x}",
        "notes_exported": "Notlarınızı masaüstüne “{name}” olarak kaydettim patron.",
        "learned": "Tamam patron, öğrendim: {x}.",
        "none_learned": "Bana henüz bir şey öğretmediniz patron. “Şunu öğren” diyerek öğretebilirsiniz.",
        "learned_list": "Bana öğrettiğiniz {n} bilgi var patron. Son öğrendiklerim: {items}",
        "forgot": "Tamam patron, şunu hafızamdan sildim: {x}",
        "not_found": "Hafızamda bununla ilgili bir kayıt bulamadım patron.",
        "which": "Neyi unutmamı istediğinizi söyler misiniz patron? Örneğin: unut, doğum günüm.",
        "unknown_personal": "Bunu bilmiyorum patron. İsterseniz “bunu hatırla” diyerek bana söyleyebilirsiniz.",
        "empty": "Hafızamda henüz kayıtlı bir bilgi yok patron. “Bunu hatırla” diyerek ekleyebilirsiniz.",
        "list": "Bana hatırlamamı söylediğiniz {n} bilgi var patron: {items}",
        "more": " Tamamını Geçmiş ve hafıza ekranında görebilirsiniz.",
    },
    "en": {
        "saved": "Got it, boss. I'll remember that.",
        "noted": "Noted, boss.",
        "no_notes": "You have no notes yet, boss. Say “take a note” to add one.",
        "notes": "You have {n} notes, boss. The latest: {items}",
        "note_deleted": "I deleted the last note, boss: {x}",
        "notes_exported": "I saved your notes to the desktop as “{name}”, boss.",
        "learned": "Got it, boss. I learned: {x}.",
        "none_learned": "You haven't taught me anything yet, boss. Say “learn that” to teach me.",
        "learned_list": "You taught me {n} things, boss. The latest: {items}",
        "forgot": "Done, boss. I removed this from my memory: {x}",
        "not_found": "I couldn't find anything about that in my memory, boss.",
        "which": "What should I forget, boss? For example: forget my birthday.",
        "unknown_personal": "I don't know that, boss. You can tell me by saying “remember that”.",
        "empty": "My memory is empty, boss. Say “remember that” to add something.",
        "list": "You asked me to remember {n} things, boss: {items}",
        "more": " You can see all of them in the history and memory screen.",
    },
}


def apply(cmd: MemoryCommand, repo: Repository, language: str,
          last_saved: tuple[int, str] | None = None) -> tuple[str, tuple[int, str] | None]:
    """(söylenecek cevap, bu oturumda en son kaydedilen (id, içerik)) döner.

    Nesnesiz "bunu unut" yalnızca bu oturumda kaydedilen son bilgiyi siler; eski bir kaydın
    "boş ver" anlamındaki bir cümleyle yanlışlıkla silinmesini önler."""
    t = TEXT.get(language, TEXT["tr"])
    if cmd.action == "remember":
        mid = repo.add_memory(cmd.payload)
        return t["saved"], (mid, cmd.payload)
    if cmd.action == "note":
        repo.add_note(cmd.payload)
        return t["noted"], last_saved
    if cmd.action == "note_list":
        notes = repo.list_notes()
        if not notes:
            return t["no_notes"], last_saved
        items = "; ".join(c.rstrip(".") for _, c, _ in notes[-LIST_SPOKEN_MAX:]) + "."
        return t["notes"].format(n=len(notes), items=items), last_saved
    if cmd.action == "note_delete_last":
        notes = repo.list_notes()
        if not notes:
            return t["no_notes"], last_saved
        nid, content, _ = notes[-1]
        repo.delete_note(nid)
        return t["note_deleted"].format(x=content.rstrip(".")), last_saved
    if cmd.action == "note_export":
        notes = repo.list_notes()
        if not notes:
            return t["no_notes"], last_saved
        from ..tools.desktop import create_on_desktop
        body = "\n".join(f"- {c}  ({created[:10]})" for _, c, created in notes)
        path = create_on_desktop("Stark notları", "dosya", body)
        return t["notes_exported"].format(name=path.name), last_saved
    if cmd.action == "learn":
        mid = repo.add_memory(cmd.payload, KNOWLEDGE)
        return t["learned"].format(x=cmd.payload.rstrip(".")), (mid, cmd.payload)
    if cmd.action == "list_learned":
        learned = repo.list_memories(KNOWLEDGE)
        if not learned:
            return t["none_learned"], last_saved
        items = "; ".join(c.rstrip(".") for _, c, _ in learned[-LIST_SPOKEN_MAX:]) + "."
        text = t["learned_list"].format(n=len(learned), items=items)
        return text + (t["more"] if len(learned) > LIST_SPOKEN_MAX else ""), last_saved
    if cmd.action == "forget_last":
        if last_saved is None or last_saved[0] not in {m[0] for m in repo.list_memories()}:
            return t["which"], None
        repo.delete_memory(last_saved[0])
        return t["forgot"].format(x=last_saved[1]), None
    if cmd.action == "forget":
        found = repo.find_memory(cmd.payload)
        if not found:
            return t["not_found"], last_saved
        repo.delete_memory(found[0])
        return t["forgot"].format(x=found[1]), (None if last_saved and last_saved[0] == found[0] else last_saved)
    if cmd.action == "list":
        memories = repo.list_memories()
        if not memories:
            return t["empty"], last_saved
        items = "; ".join(c.rstrip(".") for _, c, _ in memories[:LIST_SPOKEN_MAX]) + "."
        text = t["list"].format(n=len(memories), items=items)
        return text + (t["more"] if len(memories) > LIST_SPOKEN_MAX else ""), last_saved
    raise ValueError(cmd.action)
