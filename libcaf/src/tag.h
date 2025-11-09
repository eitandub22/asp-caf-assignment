#ifndef TAG_H
#define TAG_H

#include <string>

class Tag {
public:
    const std::string name;
    const std::string commit_hash;
    const std::string author;
    const std::string message;
    const std::time_t timestamp;

    Tag(const std::string& name, const std::string& commit_hash, const std::string& author, const std::string& message, const std::time_t timestamp)
        : name(name), commit_hash(commit_hash), author(author), message(message), timestamp(timestamp) {}
};

#endif // TAG_H