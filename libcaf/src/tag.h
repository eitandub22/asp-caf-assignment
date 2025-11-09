#ifndef TAG_H
#define TAG_H

#include <string>

class Tag {
public:
    const std::string name;
    const std::string commit_hash;
    const std::string author;
    const std::string message;
    const std::string date;

    Tag(const std::string& name, const std::string& commit_hash, const std::string& author, const std::string& message, const std::string& date)
        : name(name), commit_hash(commit_hash), author(author), message(message), date(date) {}
};

#endif // TAG_H