; --- scope captures ---

; namespace_identifier — NOT plain identifier!
(namespace_definition
  name: (namespace_identifier) @scope.ns.name)
  @scope.ns

; type_identifier — NOT plain identifier!
(class_specifier
  name: (type_identifier) @scope.class.name)
  @scope.class

(struct_specifier
  name: (type_identifier) @scope.struct.name)
  @scope.struct
