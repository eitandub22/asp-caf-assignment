#ifndef HASHTYPES_H
#define HASHTYPES_H

#include <string>

#include "blob.h"
#include "tree_record.h"
#include "tree.h"
#include "commit.h"
#include "tag.h"

std::string hash_object(const Blob& blob);
std::string hash_object(const Tree& tree);
std::string hash_object(const Commit& commit);
std::string hash_object(const Tag& tag);

#endif // HASHTYPES_H